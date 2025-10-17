from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, DateTime, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from passlib.hash import bcrypt
from typing import Optional
from datetime import datetime, timedelta
import csv
import io
import pytz
import os
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from PIL import Image

# --- Configurações ---
DATABASE_URL = "sqlite:///./atividades.db"
TIMEZONE = pytz.timezone("Europe/Lisbon")
UPLOAD_DIR = "./uploads"
MAX_BCRYPT_LEN = 72
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

# --- Servir static ---
app.mount("/static", StaticFiles(directory="web"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

security = HTTPBasic()

# --- Models ---
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True)
    senha_hash = Column(String)

class Atividade(Base):
    __tablename__ = "atividades"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer)
    data_hora = Column(DateTime)
    localizacao = Column(String)
    nome_local = Column(String)
    tipo_codigo = Column(Integer)
    tipo_texto = Column(String)
    kilometragem = Column(Integer)
    pais = Column(String)  # PT ou ES
    foto = Column(LargeBinary, nullable=True)
    foto_nome = Column(String, nullable=True)

class TipoAtividade(Base):
    __tablename__ = "tipos_atividade"
    codigo = Column(Integer, primary_key=True)
    nome = Column(String)

Base.metadata.create_all(bind=engine)

# --- Inicializar tipos ---
tipos = [
    (1, "Carga"),
    (2, "Descarga"),
    (3, "Inicio de turno"),
    (4, "Termino de turno"),
    (5, "Abastecimento"),
    (6, "Pausa 9"),
    (7, "Pausa 11"),
    (8, "Observacoes")
]
for codigo, nome in tipos:
    if not db.query(TipoAtividade).filter_by(codigo=codigo).first():
        db.add(TipoAtividade(codigo=codigo, nome=nome))
db.commit()

# --- Dependência ---
def autenticar(credentials: HTTPBasicCredentials = Depends(security)):
    usuario = db.query(Usuario).filter_by(nome=credentials.username).first()
    if not usuario or not bcrypt.verify(credentials.password[:MAX_BCRYPT_LEN], usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    return usuario

# --- Endpoints ---
@app.post("/registrar_usuario")
def registrar_usuario(nome: str = Form(...), senha: str = Form(...)):
    hashed = bcrypt.hash(senha[:MAX_BCRYPT_LEN])
    novo = Usuario(nome=nome, senha_hash=hashed)
    db.add(novo)
    try:
        db.commit()
        return {"mensagem": "Usuário registrado com sucesso"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Usuário já existe")

@app.get("/tipos_atividade")
def listar_tipos():
    tipos = db.query(TipoAtividade).all()
    return [{"codigo": t.codigo, "nome": t.nome} for t in tipos]

@app.post("/registrar_atividade")
def registrar_atividade(
    localizacao: str = Form(...),
    nome_local: str = Form(...),
    tipo_codigo: int = Form(...),
    kilometragem: int = Form(...),
    pais: str = Form("PT"),
    foto: Optional[UploadFile] = File(None),
    usuario: Usuario = Depends(autenticar)
):
    tipo = db.query(TipoAtividade).filter_by(codigo=tipo_codigo).first()
    if not tipo:
        raise HTTPException(status_code=400, detail="Tipo de atividade inválido")

    foto_bin = None
    foto_nome = None
    if foto:
        image = Image.open(foto.file)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.thumbnail((1024,1024))
        buffer = io.BytesIO()
        quality = 85
        image.save(buffer, format="JPEG", optimize=True, quality=quality)
        while buffer.tell() > 300*1024 and quality > 10:
            quality -= 5
            buffer.seek(0)
            buffer.truncate()
            image.save(buffer, format="JPEG", optimize=True, quality=quality)
        buffer.seek(0)
        foto_bin = buffer.read()
        foto_nome = foto.filename.rsplit(".",1)[0]+".jpg"

    atividade = Atividade(
        usuario_id=usuario.id,
        data_hora=datetime.now(TIMEZONE),
        localizacao=localizacao,
        nome_local=nome_local,
        tipo_codigo=tipo.codigo,
        tipo_texto=tipo.nome,
        kilometragem=kilometragem,
        pais=pais,
        foto=foto_bin,
        foto_nome=foto_nome
    )
    db.add(atividade)
    db.commit()
    return {"mensagem": "Atividade registrada com sucesso"}

@app.get("/atividades")
def listar_atividades(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    tipos: Optional[str] = None,
    usuario: Usuario = Depends(autenticar)
):
    query = db.query(Atividade).filter_by(usuario_id=usuario.id)
    
    if data_inicio:
        inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
        query = query.filter(Atividade.data_hora >= inicio_dt)
    if data_fim:
        fim_dt = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        query = query.filter(Atividade.data_hora <= fim_dt)
    
    if tipos:
        lista_tipos = [int(t) for t in tipos.split(",") if t.isdigit()]
        query = query.filter(Atividade.tipo_codigo.in_(lista_tipos))
    
    # Alterar de desc() para asc() para mostrar da mais antiga para a mais nova
    resultados = query.order_by(Atividade.data_hora.asc()).all()
    
    lista = []
    for a in resultados:
        foto_url = None
        if a.foto and a.foto_nome:
            foto_path = os.path.join("uploads", f"{a.id}_{a.foto_nome}")
            if not os.path.exists(foto_path):
                with open(foto_path, "wb") as f:
                    f.write(a.foto)
            foto_url = f"/uploads/{a.id}_{a.foto_nome}"
        lista.append({
            "id": a.id,
            "data_hora": a.data_hora.strftime("%d/%m/%Y - %H:%M:%S"),
            "localizacao": a.localizacao,
            "nome_local": a.nome_local,
            "tipo_codigo": a.tipo_codigo,
            "tipo_texto": a.tipo_texto,
            "kilometragem": a.kilometragem,
            "foto_url": foto_url,
            "pais": a.pais
        })
    return lista


@app.get("/exportar_csv")
def exportar_csv(usuario: Usuario = Depends(autenticar)):
    atividades = db.query(Atividade).filter_by(usuario_id=usuario.id).order_by(Atividade.data_hora.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Data/Hora", "Localização", "Nome do Local", "Tipo", "Kilometragem", "País"])
    for a in atividades:
        writer.writerow([
            a.data_hora.strftime("%d/%m/%Y - %H:%M:%S"),
            a.localizacao,
            a.nome_local,
            a.tipo_texto,
            a.kilometragem,
            a.pais
        ])
    return FileResponse(io.BytesIO(output.getvalue().encode("utf-8")), media_type="text/csv", filename="atividades.csv")

@app.get("/uploads/{filename}")
def pegar_foto(filename: str):
    file_path = os.path.join("uploads", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(file_path)
