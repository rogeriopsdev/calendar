import streamlit as st
import pandas as pd
import sqlite3
#from streamlit_calendar import calendar
from fpdf import FPDF
from datetime import datetime, date, timedelta
import hashlib
import calendar as cal

# ======================================
# CONFIGURAÇÃO DA PÁGINA
# ======================================
st.set_page_config(page_title="Calendário Acadêmico – IFTO", layout="wide")

st.markdown(
    """
    <h1 style='color:#008542;'>
        📅 Calendário Acadêmico – IFTO
    </h1>
    """,
    unsafe_allow_html=True
)

# ======================================
# CORES E PRIORIDADES
# ======================================

# Cores para exibição no Streamlit (hex)
UI_CORES = {
    "aula": "#008542",      # verde IFTO
    "evento": "#F2AF00",    # amarelo
    "feriado": "#D62828",   # vermelho
    "reunião": "#006666",   # verde petróleo
}

# Cores para o PDF (RGB)
PDF_CORES = {
    "aula": (0, 133, 66),        # verde IFTO
    "evento": (242, 175, 0),     # amarelo
    "feriado": (214, 40, 40),    # vermelho
    "reunião": (0, 102, 102),    # verde petróleo
}

PRIORIDADE = ["feriado", "reunião", "evento", "aula"]

# ======================================
# BANCO DE DADOS (SQLite)
# ======================================
@st.cache_resource
def get_connection():
    conn = sqlite3.connect("calendario.db", check_same_thread=False)

    # Tabela de eventos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT
        )
    """)
    conn.commit()


    # Garantir coluna 'fim'
    try:
        conn.execute("ALTER TABLE eventos ADD COLUMN fim TEXT;")
        conn.commit()
    except Exception:
        pass

    # Tabela de usuários
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL
        )
    """)
    conn.commit()

    # Tabela de semestres acadêmicos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS semestres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_semestre TEXT UNIQUE NOT NULL,
            data_inicio TEXT NOT NULL,
            data_fim TEXT NOT NULL
        )
    """)
    conn.commit()

    # Usuário admin padrão
    cursor = conn.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if cursor.fetchone() is None:
        senha_hash = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute(
            "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
            ("admin", senha_hash, "admin")
        )
        conn.commit()

    return conn

conn = get_connection()

# ======================================
# FUNÇÕES DE USUÁRIO / LOGIN
# ======================================
def autenticar_usuario(username, senha):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    cursor = conn.execute(
        "SELECT username, perfil FROM usuarios WHERE username = ? AND senha = ?",
        (username, senha_hash)
    )
    row = cursor.fetchone()
    if row:
        return {"username": row[0], "perfil": row[1]}
    return None

def criar_usuario(username, senha, perfil):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    conn.execute(
        "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
        (username, senha_hash, perfil)
    )
    conn.commit()

# ======================================
# FUNÇÕES PARA SEMESTRES ACADÊMICOS
# ======================================
def carregar_semestres():
    return pd.read_sql_query(
        "SELECT * FROM semestres ORDER BY nome_semestre",
        conn
    )

# ======================================
# CONTROLE DE SESSÃO / LOGIN
# ======================================
if "logged" not in st.session_state:
    st.session_state.logged = False
    st.session_state.username = ""
    st.session_state.perfil = ""

if not st.session_state.logged:
    st.markdown("## 🔐 Login Necessário")

    username_input = st.text_input("Usuário")
    password_input = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        user = autenticar_usuario(username_input, password_input)
        if user:
            st.session_state.logged = True
            st.session_state.username = user["username"]
            st.session_state.perfil = user["perfil"]
            st.success(f"Bem-vindo, {user['username']}! 🎉")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")

    st.stop()

# Já logado
st.sidebar.markdown(f"👤 Usuário: **{st.session_state.username}** ({st.session_state.perfil})")
if st.sidebar.button("Sair"):
    st.session_state.logged = False
    st.session_state.username = ""
    st.session_state.perfil = ""
    st.rerun()

# ======================================
# GERENCIAMENTO DE USUÁRIOS E SEMESTRES (ADMIN)
# ======================================
if st.session_state.perfil == "admin":
    st.sidebar.markdown("### 👥 Gerenciar usuários")
    with st.sidebar.expander("Criar novo usuário"):
        novo_user = st.text_input("Novo usuário", key="novo_user")
        nova_senha = st.text_input("Senha", key="nova_senha", type="password")
        novo_perfil = st.selectbox("Perfil", ["admin", "editor", "viewer"], key="novo_perfil")
        if st.button("Adicionar usuário"):
            if novo_user.strip() == "" or nova_senha.strip() == "":
                st.sidebar.error("Preencha usuário e senha.")
            else:
                try:
                    criar_usuario(novo_user, nova_senha, novo_perfil)
                    st.sidebar.success("Usuário criado com sucesso!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.sidebar.error("Usuário já existe.")

    st.sidebar.markdown("### 📚 Semestres Acadêmicos")

    df_sem = carregar_semestres()

    # --- ADICIONAR SEMESTRE ---
    with st.sidebar.expander("➕ Adicionar semestre"):
        novo_nome = st.text_input("Nome do semestre (ex: 2025/1)", key="sem_nome")
        novo_ini = st.date_input("Data de início", key="sem_ini")
        novo_fim = st.date_input("Data de fim", key="sem_fim")

        if st.button("Salvar semestre", key="btn_add_sem"):
            if novo_nome.strip() == "":
                st.sidebar.error("Informe um nome para o semestre.")
            elif novo_ini > novo_fim:
                st.sidebar.error("Data de início não pode ser maior que a data de fim.")
            else:
                try:
                    conn.execute(
                        "INSERT INTO semestres (nome_semestre, data_inicio, data_fim) VALUES (?, ?, ?)",
                        (novo_nome, novo_ini.isoformat(), novo_fim.isoformat())
                    )
                    conn.commit()
                    st.sidebar.success("Semestre adicionado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.sidebar.error("Este semestre já existe.")

    # --- EDITAR SEMESTRE ---
    with st.sidebar.expander("✏️ Editar semestre"):
        if df_sem.empty:
            st.sidebar.info("Nenhum semestre cadastrado.")
        else:
            sem_escolhido = st.selectbox("Escolha o semestre", df_sem["nome_semestre"], key="edit_sem")
            row_sem = df_sem[df_sem["nome_semestre"] == sem_escolhido].iloc[0]

            novo_ini_ed = st.date_input(
                "Novo início",
                pd.to_datetime(row_sem["data_inicio"]).date(),
                key="edit_ini"
            )
            novo_fim_ed = st.date_input(
                "Novo fim",
                pd.to_datetime(row_sem["data_fim"]).date(),
                key="edit_fim"
            )

            if st.button("Salvar alterações", key="btn_edit_sem"):
                if novo_ini_ed > novo_fim_ed:
                    st.sidebar.error("Data inicial não pode ser maior que a final.")
                else:
                    conn.execute(
                        "UPDATE semestres SET data_inicio=?, data_fim=? WHERE nome_semestre=?",
                        (novo_ini_ed.isoformat(), novo_fim_ed.isoformat(), sem_escolhido)
                    )
                    conn.commit()
                    st.sidebar.success("Semestre atualizado!")
                    st.rerun()

    # --- EXCLUIR SEMESTRE ---
    with st.sidebar.expander("🗑️ Excluir semestre"):
        if df_sem.empty:
            st.sidebar.info("Nenhum semestre para excluir.")
        else:
            sem_excluir = st.selectbox("Selecione", df_sem["nome_semestre"], key="del_sem")

            if st.button("Excluir semestre", key="btn_del_sem"):
                conn.execute("DELETE FROM semestres WHERE nome_semestre=?", (sem_excluir,))
                conn.commit()
                st.sidebar.success("Semestre excluído!")
                st.rerun()

else:
    st.sidebar.markdown("### 📚 Semestres Acadêmicos")
    st.sidebar.info("Apenas administradores podem gerenciar semestres.")

# ======================================
# FUNÇÕES DE EVENTOS
# ======================================
def carregar_eventos():
    df = pd.read_sql_query("SELECT * FROM eventos ORDER BY date(data)", conn)
    if df.empty:
        return df

    if "fim" not in df.columns:
        df["fim"] = df["data"]
    df["fim"] = df["fim"].fillna(df["data"])

    df["data"] = pd.to_datetime(df["data"])
    df["fim"] = pd.to_datetime(df["fim"])
    return df

def inserir_evento(data_inicio, tipo, titulo, descricao, data_fim=None):
    if data_fim is None:
        data_fim = data_inicio
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO eventos (data, tipo, titulo, descricao, fim) VALUES (?, ?, ?, ?, ?)",
        (str(data_inicio), tipo, titulo, descricao, str(data_fim))
    )
    conn.commit()

def atualizar_evento(id_evento, data_inicio, tipo, titulo, descricao, data_fim):
    cur = conn.cursor()
    cur.execute(
        "UPDATE eventos SET data = ?, tipo = ?, titulo = ?, descricao = ?, fim = ? WHERE id = ?",
        (str(data_inicio), tipo, titulo, descricao, str(data_fim), id_evento)
    )
    conn.commit()

def excluir_evento(id_evento):
    cur = conn.cursor()
    cur.execute("DELETE FROM eventos WHERE id = ?", (id_evento,))
    conn.commit()

# ======================================
# SELEÇÃO DE SEMESTRE ACADÊMICO (VISUALIZAÇÃO)
# ======================================
st.markdown("## 🎓 Seleção de Semestre Acadêmico")

df_semestres = carregar_semestres()
inicio_sem = None
fim_sem = None
semestre_atual = None

if df_semestres.empty:
    st.warning("Nenhum semestre cadastrado. Cadastre na barra lateral (admin).")
else:
    semestre_atual = st.selectbox(
        "Selecione o semestre acadêmico",
        df_semestres["nome_semestre"].tolist()
    )

    dados_sem = df_semestres[df_semestres["nome_semestre"] == semestre_atual].iloc[0]
    inicio_sem = pd.to_datetime(dados_sem["data_inicio"]).date()
    fim_sem = pd.to_datetime(dados_sem["data_fim"]).date()

    st.info(
        f"📘 Período do semestre **{semestre_atual}**: "
        f"{inicio_sem.strftime('%d/%m/%Y')} a {fim_sem.strftime('%d/%m/%Y')}"
    )
    st.caption("A visualização (dashboard, calendário e PDF) será filtrada por este intervalo. O cadastro de eventos pode usar qualquer data.")

# ======================================
# SIDEBAR – CRUD EVENTOS (somente admin/editor)
# ======================================
df_eventos_all = carregar_eventos()

if st.session_state.perfil in ["admin", "editor"]:
    st.sidebar.markdown("## ⚙️ Gerenciamento de eventos")

    operacao = st.sidebar.radio(
        "Operação",
        ["Adicionar", "Editar", "Excluir"],
        index=0
    )

    # ---------- ADICIONAR ----------
    if operacao == "Adicionar":
        st.sidebar.markdown("### ➕ Adicionar evento (com período)")

        data_inicio = st.sidebar.date_input("Data de início", value=date.today())
        data_fim = st.sidebar.date_input("Data de fim", value=date.today())
        tipo_new = st.sidebar.selectbox(
            "Tipo do evento",
            ["aula", "evento", "feriado", "reunião"]
        )
        titulo_new = st.sidebar.text_input("Título")
        descricao_new = st.sidebar.text_area("Descrição")

        if st.sidebar.button("Salvar evento"):
            if data_fim < data_inicio:
                st.sidebar.error("A data final não pode ser menor que a data inicial.")
            elif titulo_new.strip() == "":
                st.sidebar.error("Informe um título válido.")
            else:
                inserir_evento(data_inicio, tipo_new, titulo_new, descricao_new, data_fim)
                st.sidebar.success("Evento salvo com sucesso!")
                st.rerun()

    # ---------- EDITAR ----------
    elif operacao == "Editar":
        st.sidebar.markdown("### ✏️ Editar evento")
        if df_eventos_all.empty:
            st.sidebar.info("Nenhum evento cadastrado.")
        else:
            df_eventos_all["label"] = df_eventos_all.apply(
                lambda r: f"{r['id']} - {r['data'].strftime('%d/%m/%Y')} a {r['fim'].strftime('%d/%m/%Y')} - {r['titulo']}",
                axis=1
            )
            escolhido = st.sidebar.selectbox("Selecione o evento", df_eventos_all["label"])
            id_escolhido = int(escolhido.split(" - ")[0])
            row_evt = df_eventos_all[df_eventos_all["id"] == id_escolhido].iloc[0]

            with st.sidebar.form("form_editar"):
                data_edit_inicio = st.date_input("Data de início", row_evt["data"].date())
                data_edit_fim = st.date_input("Data de fim", row_evt["fim"].date())
                tipo_edit = st.selectbox(
                    "Tipo",
                    ["aula", "evento", "feriado", "reunião"],
                    index=["aula", "evento", "feriado", "reunião"].index(row_evt["tipo"])
                )
                titulo_edit = st.text_input("Título", value=row_evt["titulo"])
                descricao_edit = st.text_area("Descrição", value=row_evt["descricao"] or "")

                salvar = st.form_submit_button("Salvar alterações")

            if salvar:
                if data_edit_fim < data_edit_inicio:
                    st.sidebar.error("A data final não pode ser menor que a inicial.")
                elif titulo_edit.strip() == "":
                    st.sidebar.error("Título inválido.")
                else:
                    atualizar_evento(
                        id_escolhido,
                        data_edit_inicio,
                        tipo_edit,
                        titulo_edit,
                        descricao_edit,
                        data_edit_fim
                    )
                    st.sidebar.success("Evento atualizado!")
                    st.rerun()

    # ---------- EXCLUIR ----------
    elif operacao == "Excluir":
        st.sidebar.markdown("### 🗑️ Excluir evento")

        if df_eventos_all.empty:
            st.sidebar.info("Nenhum evento cadastrado.")
        else:
            df_eventos_all["label"] = df_eventos_all.apply(
                lambda r: f"{r['id']} - {r['data'].strftime('%d/%m/%Y')} a {r['fim'].strftime('%d/%m/%Y')} - {r['titulo']}",
                axis=1
            )
            escolhido = st.sidebar.selectbox("Selecione o evento", df_eventos_all["label"])
            id_escolhido = int(escolhido.split(" - ")[0])

            if st.sidebar.button("Excluir definitivamente"):
                excluir_evento(id_escolhido)
                st.sidebar.success("Evento excluído.")
                st.rerun()
else:
    st.sidebar.warning("Você possui permissão apenas para visualizar o calendário e o dashboard.")

# ======================================
# DASHBOARD (FILTRADO PELO SEMESTRE, SE HOUVER)
# ======================================
st.markdown("## 📊 Dashboard")

df_eventos = carregar_eventos()

if inicio_sem and fim_sem:
    df_eventos_sem = df_eventos[
        (df_eventos["data"].dt.date <= fim_sem) &
        (df_eventos["fim"].dt.date >= inicio_sem)
    ]
else:
    df_eventos_sem = df_eventos.copy()

if df_eventos_sem.empty:
    st.info("Nenhum evento cadastrado para o semestre selecionado.")
else:
    col1, col2, col3 = st.columns(3)

    col1.metric("Total de eventos", len(df_eventos_sem))
    col2.metric("Aulas", (df_eventos_sem["tipo"] == "aula").sum())
    col3.metric("Feriados", (df_eventos_sem["tipo"] == "feriado").sum())

    df_eventos_sem["mes"] = df_eventos_sem["data"].dt.to_period("M").astype(str)

    st.markdown("### Eventos por tipo")
    st.bar_chart(df_eventos_sem["tipo"].value_counts())

    st.markdown("### Eventos por mês (data de início)")
    st.line_chart(df_eventos_sem.groupby("mes")["id"].count())

    st.markdown("### Tabela de eventos do semestre")
    df_show = df_eventos_sem[["id", "data", "fim", "tipo", "titulo", "descricao"]].copy()
    df_show["data"] = df_show["data"].dt.strftime("%d/%m/%Y")
    df_show["fim"] = df_show["fim"].dt.strftime("%d/%m/%Y")
    st.dataframe(df_show, use_container_width=True)

# ======================================
# EVENTOS PARA O CALENDÁRIO (FILTRADO)
# ======================================
df_eventos_cal = carregar_eventos()

if inicio_sem and fim_sem:
    df_eventos_cal = df_eventos_cal[
        (df_eventos_cal["data"].dt.date <= fim_sem) &
        (df_eventos_cal["fim"].dt.date >= inicio_sem)
    ]

eventos_global = []
if not df_eventos_cal.empty:
    for _, row in df_eventos_cal.iterrows():
        cor_hex = UI_CORES.get(row["tipo"], "#555555")

        # 'fim' inclusivo no banco → exclusivo no calendário (+1 dia)
        end_exclusive = (row["fim"] + timedelta(days=1)).strftime("%Y-%m-%d")

        eventos_global.append({
            "title": row["titulo"],
            "start": row["data"].strftime("%Y-%m-%d"),
            "end": end_exclusive,
            "description": row["descricao"] or "",
            "color": cor_hex
        })

# Ano base para título do calendário
if not df_eventos_cal.empty:
    ano_base = int(df_eventos_cal["data"].dt.year.mode()[0])
else:
    ano_base = date.today().year

# ======================================
# CALENDÁRIO ANUAL – 12 MESES (VISUAL)
# ======================================
st.markdown("## 🗓️ Visualização em calendário – 12 meses")

meses_nomes = [
    "Janeiro", "Fevereiro", "Março",
    "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro",
    "Outubro", "Novembro", "Dezembro"
]

for linha in range(0, 12, 3):
    col1, col2, col3 = st.columns(3)

    # --------- COLUNA 1 ---------
    with col1:
        mes_num = linha + 1
        st.subheader(f"{meses_nomes[linha]} / {ano_base}")
        cal_state = calendar(
            events=eventos_global,
            options={
                "initialView": "dayGridMonth",
                "initialDate": f"{ano_base}-{mes_num:02d}-01",
                "locale": "pt-br",
                "height": 350,
                "headerToolbar": {"left": "", "center": "", "right": ""},
                "dateClick": True
            },
            key=f"mes_{mes_num}"
        )

        if cal_state and isinstance(cal_state, dict) and cal_state.get("callback") == "dateClick":
            if st.session_state.perfil in ["admin", "editor"]:
                dia = cal_state["dateClick"]["date"]
                try:
                    data_click = datetime.fromisoformat(dia).date()
                except Exception:
                    data_click = date.today()

                st.markdown(f"### ➕ Novo evento em {data_click.strftime('%d/%m/%Y')}")
                with st.form(f"add_{mes_num}_1"):
                    tipo = st.selectbox("Tipo", ["aula", "evento", "feriado", "reunião"])
                    data_inicio_click = st.date_input("Início", value=data_click)
                    data_fim_click = st.date_input("Fim", value=data_click)
                    titulo = st.text_input("Título")
                    descricao = st.text_area("Descrição")
                    salvar = st.form_submit_button("Salvar")

                if salvar:
                    if data_fim_click < data_inicio_click:
                        st.error("Data final não pode ser menor que a inicial.")
                    elif titulo.strip() == "":
                        st.error("Informe um título válido.")
                    else:
                        inserir_evento(data_inicio_click, tipo, titulo, descricao, data_fim_click)
                        st.success("Evento cadastrado!")
                        st.rerun()

    # --------- COLUNA 2 ---------
    with col2:
        mes_num = linha + 2
        st.subheader(f"{meses_nomes[linha + 1]} / {ano_base}")
        cal_state = calendar(
            events=eventos_global,
            options={
                "initialView": "dayGridMonth",
                "initialDate": f"{ano_base}-{mes_num:02d}-01",
                "locale": "pt-br",
                "height": 350,
                "headerToolbar": {"left": "", "center": "", "right": ""},
                "dateClick": True
            },
            key=f"mes_{mes_num}"
        )

        if cal_state and isinstance(cal_state, dict) and cal_state.get("callback") == "dateClick":
            if st.session_state.perfil in ["admin", "editor"]:
                dia = cal_state["dateClick"]["date"]
                try:
                    data_click = datetime.fromisoformat(dia).date()
                except Exception:
                    data_click = date.today()

                st.markdown(f"### ➕ Novo evento em {data_click.strftime('%d/%m/%Y')}")
                with st.form(f"add_{mes_num}_2"):
                    tipo = st.selectbox("Tipo", ["aula", "evento", "feriado", "reunião"])
                    data_inicio_click = st.date_input("Início", value=data_click)
                    data_fim_click = st.date_input("Fim", value=data_click)
                    titulo = st.text_input("Título")
                    descricao = st.text_area("Descrição")
                    salvar = st.form_submit_button("Salvar")

                if salvar:
                    if data_fim_click < data_inicio_click:
                        st.error("Data final não pode ser menor que a inicial.")
                    elif titulo.strip() == "":
                        st.error("Informe um título válido.")
                    else:
                        inserir_evento(data_inicio_click, tipo, titulo, descricao, data_fim_click)
                        st.success("Evento cadastrado!")
                        st.rerun()

    # --------- COLUNA 3 ---------
    with col3:
        mes_num = linha + 3
        st.subheader(f"{meses_nomes[linha + 2]} / {ano_base}")
        cal_state = calendar(
            events=eventos_global,
            options={
                "initialView": "dayGridMonth",
                "initialDate": f"{ano_base}-{mes_num:02d}-01",
                "locale": "pt-br",
                "height": 350,
                "headerToolbar": {"left": "", "center": "", "right": ""},
                "dateClick": True
            },
            key=f"mes_{mes_num}"
        )

        if cal_state and isinstance(cal_state, dict) and cal_state.get("callback") == "dateClick":
            if st.session_state.perfil in ["admin", "editor"]:
                dia = cal_state["dateClick"]["date"]
                try:
                    data_click = datetime.fromisoformat(dia).date()
                except Exception:
                    data_click = date.today()

                st.markdown(f"### ➕ Novo evento em {data_click.strftime('%d/%m/%Y')}")
                with st.form(f"add_{mes_num}_3"):
                    tipo = st.selectbox("Tipo", ["aula", "evento", "feriado", "reunião"])
                    data_inicio_click = st.date_input("Início", value=data_click)
                    data_fim_click = st.date_input("Fim", value=data_click)
                    titulo = st.text_input("Título")
                    descricao = st.text_area("Descrição")
                    salvar = st.form_submit_button("Salvar")

                if salvar:
                    if data_fim_click < data_inicio_click:
                        st.error("Data final não pode ser menor que a inicial.")
                    elif titulo.strip() == "":
                        st.error("Informe um título válido.")
                    else:
                        inserir_evento(data_inicio_click, tipo, titulo, descricao, data_fim_click)
                        st.success("Evento cadastrado!")
                        st.rerun()

# ======================================
# EXPORTAÇÃO PARA PDF – CALENDÁRIO COMPLETO (SEMESTRE)
# ======================================
st.markdown("## 📄 Exportar calendário para PDF")

def gerar_pdf(df, titulo_extra=None):
    # Determinar ano base
    if df.empty:
        ano_base = date.today().year
    else:
        ano_base = int(df["data"].dt.year.mode()[0])
        df = df.copy()
        df = df[df["data"].dt.year == ano_base]

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)

    nomes_meses = [
        "Janeiro", "Fevereiro", "Março",
        "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro",
        "Outubro", "Novembro", "Dezembro"
    ]

    trimestres = [
        (1, 2, 3),
        (4, 5, 6),
        (7, 8, 9),
        (10, 11, 12)
    ]

    # Eventos por dia (para colorir períodos)
    eventos_por_dia = {}

    for _, row in df.iterrows():
        inicio = row["data"].date()
        fim = row["fim"].date()
        dia = inicio
        while dia <= fim:
            eventos_por_dia.setdefault(dia, []).append(row)
            dia += timedelta(days=1)

    def desenhar_mes_colorido(pdf, ano, mes, x, y, w, h, eventos_mes):
        cal.setfirstweekday(cal.MONDAY)
        semanas = cal.monthcalendar(ano, mes)

        pdf.set_font("DejaVu", size=10)
        pdf.set_xy(x, y)
        pdf.cell(w, 6, txt=nomes_meses[mes - 1].upper(), ln=False, align="C")

        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        header_y = y + 7
        cell_w = w / 7
        cell_h = (h - 12) / 6

        pdf.set_font("DejaVu", size=7)
        for i, ds in enumerate(dias_semana):
            pdf.set_xy(x + i * cell_w, header_y)
            pdf.cell(cell_w, 5, txt=ds, border=1, align="C")

        for linha_idx, semana in enumerate(semanas):
            for col_idx, dia in enumerate(semana):
                cx = x + col_idx * cell_w
                cy = header_y + 5 + linha_idx * cell_h

                pdf.rect(cx, cy, cell_w, cell_h)

                if dia > 0:
                    data_atual = date(ano, mes, dia)

                    cor = None
                    for tipo in PRIORIDADE:
                        if data_atual in eventos_mes[tipo]:
                            cor = PDF_CORES[tipo]
                            break

                    if cor:
                        pdf.set_fill_color(*cor)
                        pdf.rect(cx, cy, cell_w, cell_h, style="F")
                        pdf.set_text_color(255, 255, 255)
                    else:
                        pdf.set_text_color(0, 0, 0)

                    pdf.set_xy(cx + 1, cy + 1)
                    pdf.cell(cell_w - 2, 4, txt=str(dia))

    # Montando páginas
    for idx_trim, trio in enumerate(trimestres, start=1):
        pdf.add_page()
        margin_x = 10
        margin_y = 10
        titulo_h = 10
        gap_x = 5

        pdf.set_font("DejaVu", size=14)
        pdf.set_xy(margin_x, margin_y)

        titulo_base = f"Calendário Acadêmico – {ano_base} | Trimestre {idx_trim}"
        if titulo_extra:
            titulo_final = f"{titulo_base} | {titulo_extra}"
        else:
            titulo_final = titulo_base

        pdf.cell(0, 8, txt=titulo_final, ln=True, align="C")

        topo_cal = margin_y + titulo_h + 3
        largura_util = pdf.w - 2 * margin_x
        largura_mes = (largura_util - 2 * gap_x) / 3
        altura_mes = 80

        # Desenhar 3 meses
        for i, mes in enumerate(trio):
            eventos_mes = {tp: set() for tp in PRIORIDADE}

            for dia, lista_eventos in eventos_por_dia.items():
                if dia.month == mes and dia.year == ano_base:
                    tipos = [str(ev["tipo"]) for ev in lista_eventos]
                    for tp in PRIORIDADE:
                        if tp in tipos:
                            eventos_mes[tp].add(dia)

            x = margin_x + i * (largura_mes + gap_x)
            y = topo_cal

            desenhar_mes_colorido(pdf, ano_base, mes, x, y, largura_mes, altura_mes, eventos_mes)

        # Lista de eventos do trimestre
        pdf.set_font("DejaVu", size=11)
        pdf.set_xy(margin_x, topo_cal + altura_mes + 6)
        pdf.cell(0, 6, txt="Eventos do trimestre (ordenados por data):", ln=True)

        pdf.set_font("DejaVu", size=9)

        df_trim = df[df["data"].dt.month.isin(trio)].sort_values("data")

        if df_trim.empty:
            pdf.set_x(margin_x)
            pdf.cell(0, 5, txt="• Não há eventos para este trimestre.", ln=True)
        else:
            for _, row in df_trim.iterrows():
                ini = row["data"].strftime("%d/%m/%Y")
                fim = row["fim"].strftime("%d/%m/%Y")
                if ini == fim:
                    periodo = ini
                else:
                    periodo = f"{ini} a {fim}"

                linha = f"• {periodo} – {row['tipo']} – {row['titulo']}"
                pdf.set_x(margin_x)
                pdf.multi_cell(pdf.w - 2 * margin_x, 5, txt=linha)

    caminho = "calendario_ifto.pdf"
    pdf.output(caminho)
    return caminho

# Preparar dados para exportação
df_export = carregar_eventos()
if inicio_sem and fim_sem:
    df_export = df_export[
        (df_export["data"].dt.date <= fim_sem) &
        (df_export["fim"].dt.date >= inicio_sem)
    ]

if df_export.empty:
    st.warning(
        "⚠️ Não há eventos cadastrados para o semestre selecionado. "
        "O PDF será gerado apenas com o calendário em branco."
    )

gerar = st.button("📄 Gerar PDF do calendário do semestre")

if gerar:
    titulo_extra = semestre_atual if semestre_atual else None
    caminho = gerar_pdf(df_export, titulo_extra=titulo_extra)
    with open(caminho, "rb") as f:
        st.download_button(
            label="⬇️ Baixar arquivo PDF",
            data=f,
            file_name=f"calendario_IFTO_{semestre_atual or 'ano'}.pdf",
            mime="application/pdf"
        )
