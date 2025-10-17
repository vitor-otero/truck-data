const BASE_URL = "http://217.72.207.97:8000"; // Substitua pelo IP do servidor
let usuario = null;
let senha = null;
let localizacao = "PT"; // Sempre pre-selecionado Portugal

window.onload = function() {
    const u = localStorage.getItem("usuario");
    const s = localStorage.getItem("senha");
    if(u && s){
        usuario = u; senha = s;
        document.getElementById("login-box").classList.add("hidden");
        document.getElementById("dashboard").classList.remove("hidden");
        document.getElementById("nome_usuario").innerText = usuario;
        carregarTipos();
        carregarFiltros();
        listarAtividades();
    } else {
        carregarTipos();
        carregarFiltros();
    }
};

function registrarUsuario() {
    const nome = document.getElementById("novo_nome").value;
    const senhaInput = document.getElementById("nova_senha").value;
    fetch(`${BASE_URL}/registrar_usuario`, {
        method: "POST",
        body: new URLSearchParams({ nome: nome, senha: senhaInput })
    })
    .then(res => res.json())
    .then(data => document.getElementById("msg_usuario").innerText = data.mensagem || data.detail);
}

function login() {
    usuario = document.getElementById("login_nome").value;
    senha = document.getElementById("login_senha").value;
    fetch(`${BASE_URL}/atividades`, {
        headers: { "Authorization": "Basic " + btoa(usuario + ":" + senha) }
    })
    .then(res => {
        if(res.status === 401) { document.getElementById("msg_login").innerText = "Usuário ou senha incorretos"; return null; }
        return res.json().catch(() => []);
    })
    .then(data => {
        if(data !== null){
            document.getElementById("login-box").classList.add("hidden");
            document.getElementById("dashboard").classList.remove("hidden");
            document.getElementById("nome_usuario").innerText = usuario;
            localStorage.setItem("usuario", usuario);
            localStorage.setItem("senha", senha);
            carregarTipos();
            carregarFiltros();
            listarAtividades();
        }
    }).catch(err => console.error(err));
}

function logout() {
    usuario = null; senha = null;
    localStorage.removeItem("usuario"); localStorage.removeItem("senha");
    document.getElementById("dashboard").classList.add("hidden");
    document.getElementById("login-box").classList.remove("hidden");
    document.getElementById("login_nome").value = "";
    document.getElementById("login_senha").value = "";
}

function carregarTipos() {
    fetch(`${BASE_URL}/tipos_atividade`).then(r=>r.json()).then(data=>{
        const tipoSelect = document.getElementById("tipo_codigo"); tipoSelect.innerHTML="";
        data.forEach(t=>{ const opt=document.createElement("option"); opt.value=t.codigo; opt.text=t.nome; tipoSelect.appendChild(opt); });
    });
}

function carregarFiltros() {
    fetch(`${BASE_URL}/tipos_atividade`).then(r=>r.json()).then(data=>{
        const filtro = document.getElementById("filtro_tipos"); filtro.innerHTML="";
        data.forEach(t=>{ const opt=document.createElement("option"); opt.value=t.codigo; opt.text=t.nome; filtro.appendChild(opt); });
    });
}

function selecionarLocal(pais){
    localizacao = pais;
    document.querySelectorAll(".flag-btn").forEach(btn => btn.classList.remove("selected"));
    document.getElementById("btn-" + pais).classList.add("selected");
}

function registrarAtividade() {
    const formData = new FormData();
    formData.append("localizacao", localizacao);
    formData.append("nome_local", document.getElementById("nome_local").value);
    formData.append("tipo_codigo", document.getElementById("tipo_codigo").value);
    formData.append("kilometragem", document.getElementById("kilometragem").value);

    const fotoInput = document.getElementById("foto");
    if(fotoInput.files.length>0) formData.append("foto", fotoInput.files[0]);

    fetch(`${BASE_URL}/registrar_atividade`, {
        method:"POST", body:formData, headers:{ "Authorization":"Basic "+btoa(usuario+":"+senha) }
    }).then(res=>res.json()).then(data=>{
        const msg = document.getElementById("msg_atividade");
        msg.innerText = data.mensagem || data.detail;
        setTimeout(()=>msg.innerText="", 10000); // Apaga mensagem após 10s
        document.getElementById("nome_local").value="";
        document.getElementById("tipo_codigo").selectedIndex=0;
        document.getElementById("kilometragem").value="";
        document.getElementById("foto").value="";
        selecionarLocal("PT"); // resetar sempre para PT
        listarAtividades();
    });
}

function listarAtividades() {
    const inicio=document.getElementById("filtro_data_inicio").value;
    const fim=document.getElementById("filtro_data_fim").value;
    const tiposSelect=document.getElementById("filtro_tipos");
    const tiposSelecionados=Array.from(tiposSelect.selectedOptions).map(o=>o.value).join(",");

    let url=`${BASE_URL}/atividades?`;
    if(inicio) url+=`data_inicio=${inicio}&`;
    if(fim) url+=`data_fim=${fim}&`;
    if(tiposSelecionados) url+=`tipos=${tiposSelecionados}`;

    fetch(url, { headers:{ "Authorization":"Basic "+btoa(usuario+":"+senha) } })
    .then(res=>res.json())
    .then(data=>{
        const ul=document.getElementById("lista_atividades"); ul.innerHTML="";
        data.forEach(a=>{
            const li=document.createElement("li");
            const flag = a.localizacao === "PT" ? "🇵🇹" : "🇪🇸";
            li.innerHTML=`<strong>${a.data_hora}</strong> - ${flag} - ${a.nome_local} - ${a.tipo_texto} (${a.kilometragem} km) ${a.foto_url?`<a href='${BASE_URL}${a.foto_url}' target='_blank'>Ver foto</a>`:""}`;
            ul.appendChild(li);
        });
    });
}

function removerFiltros() {
    document.getElementById("filtro_data_inicio").value="";
    document.getElementById("filtro_data_fim").value="";
    document.getElementById("filtro_tipos").selectedIndex=-1;
    listarAtividades();
}

function exportarCSV() {
    fetch(`${BASE_URL}/exportar_csv`, { headers:{ "Authorization":"Basic "+btoa(usuario+":"+senha) } })
    .then(res=>res.blob())
    .then(blob=>{
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download="atividades.csv"; document.body.appendChild(a); a.click(); a.remove();
    });
}
