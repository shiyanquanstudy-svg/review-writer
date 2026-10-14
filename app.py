import streamlit as st
from src.agents.parse_instruction import parse_instruction
from src.db.db_helper import init_db, save_spec

st.set_page_config(page_title="自动化综述撰写平台", layout="wide")
st.title("自动化综述撰写平台")
st.caption("输入自然语言综述指令，平台将自动解析、检索、写作。")

init_db()

instruction = st.text_area(
    "请输入综述撰写指令",
    height=200,
    placeholder="例如：帮我撰写一个综述，临床三期抗抑郁药——JS1-1-01片的发展史……",
)

if st.button("解析指令", type="primary"):
    if not instruction.strip():
        st.warning("请先输入指令")
    else:
        with st.spinner("正在解析指令..."):
            try:
                spec = parse_instruction(instruction)
                rid = save_spec(instruction, spec.model_dump())
                st.success(f"解析成功，已保存 id={rid}")
                st.json(spec.model_dump())
            except Exception as e:
                st.error(f"解析失败：{e}")