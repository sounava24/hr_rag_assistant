import requests
import streamlit as st

API = "http://127.0.0.1:8000"

st.set_page_config(page_title="HR Policy Assistant", page_icon="📄")
st.title("Interview Purpose - RAG HR Assistant")
st.caption("Answers come only from the uploaded policies.")

# --- Sidebar: role flag, upload (admin only), document list ---
role = st.sidebar.radio("Role", ["employee", "admin"])

if role == "admin":
    st.sidebar.subheader("Upload policy")
    f = st.sidebar.file_uploader("Markdown or text", type=["md", "txt"])
    if f and st.sidebar.button("Upload and index"):
        try:
            r = requests.post(
                f"{API}/upload",
                headers={"x-role": role},
                files={"file": (f.name, f.getvalue(), "text/markdown")},
                timeout=120,
            )
            if r.status_code == 200:
                st.sidebar.success(f"Indexed {r.json()['total_chunks']} chunks")
            else:
                st.sidebar.error(r.json().get("detail", r.text))
        except requests.exceptions.RequestException as e:
            st.sidebar.error(f"Server not reachable: {e}")

try:
    docs = requests.get(f"{API}/documents", timeout=10).json()
    st.sidebar.subheader("Indexed documents")
    for d in docs:
        st.sidebar.write("•", d)
except requests.exceptions.RequestException:
    st.sidebar.error("API not running. Start it first.")

# --- Main: ask a question ---
with st.form("ask"):
    question = st.text_input("Ask a policy question",
                             placeholder="e.g. What is the casual leave carry-forward limit?")
    submitted = st.form_submit_button("Ask")

if submitted:
    try:
        with st.spinner("Searching policies..."):
            r = requests.post(f"{API}/ask", json={"question": question}, timeout=60)
        if r.status_code != 200:
            st.error(f"Error {r.status_code}: {r.text}")
        else:
            data = r.json()
            if data["found"]:
                st.success(data["answer"])
                st.subheader("Sources")
                for c in data["citations"]:
                    with st.expander(f'{c["doc_name"]}  ›  {c["section"]}'):
                        st.write(c["snippet"])
            else:
                st.warning(data["answer"])
    except requests.exceptions.RequestException as e:
        st.error(f"Server not reachable: {e}")