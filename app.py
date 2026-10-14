import json
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="自动化综述撰写平台", layout="wide")

from src.db.db_helper import init_db, get_conn, save_spec
from src.schemas import ReviewSpec
from src.agents.parse_instruction import parse_instruction
from src.agents.run_search import run_search
from src.agents.extract_info import extract_and_save
from src.agents.generate_outline import generate_outline
from src.agents.write_section import write_all
from src.agents.verify_citations import verify_draft
from src.agents.assemble_review import assemble

init_db()

st.title("自动化综述撰写平台")
st.caption("自然语言指令 → 自动检索 → 自动写作 → 自动核查 → 输出 Markdown 综述")

# ---------------- Session State ----------------
if "spec" not in st.session_state:
    st.session_state.spec = None
if "instruction" not in st.session_state:
    st.session_state.instruction = ""
if "search_summary" not in st.session_state:
    st.session_state.search_summary = None
if "outline" not in st.session_state:
    st.session_state.outline = None
if "drafts" not in st.session_state:
    st.session_state.drafts = {}
if "verify_results" not in st.session_state:
    st.session_state.verify_results = {}
if "final_markdown" not in st.session_state:
    st.session_state.final_markdown = ""

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("进度")
    stages = [
        ("① 解析指令", st.session_state.spec is not None),
        ("② 检索", st.session_state.search_summary is not None),
        ("③ 提取", st.session_state.outline is not None),
        ("④ 大纲", st.session_state.outline is not None),
        ("⑤ 写作", len(st.session_state.drafts) > 0),
        ("⑥ 核查", len(st.session_state.verify_results) > 0),
        ("⑦ 组装", bool(st.session_state.final_markdown)),
    ]
    for name, done in stages:
        icon = "[done]" if done else "[    ]"
        st.write(f"{icon} {name}")

    st.divider()
    if st.button("清空全部并重新开始", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ---------------- Tabs ----------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "① 指令", "② 检索", "③ 提取", "④ 大纲", "⑤ 写作", "⑥ 核查", "⑦ 组装"
])

# ==================== Tab 1 ====================
with tab1:
    st.header("Step 1：输入综述指令")
    instruction = st.text_area(
        "自然语言指令",
        value=st.session_state.instruction,
        height=220,
        placeholder="例如：帮我撰写一个综述，临床三期抗抑郁药——JS1-1-01片的发展史……",
    )

    if st.button("解析指令", type="primary", key="btn_parse"):
        if not instruction.strip():
            st.warning("请先输入指令")
        else:
            with st.spinner("解析中..."):
                spec = parse_instruction(instruction)
                rid = save_spec(instruction, spec.model_dump())
                st.session_state.spec = spec
                st.session_state.instruction = instruction
            st.success(f"解析完成，已保存 spec id={rid}")

    if st.session_state.spec:
        spec = st.session_state.spec
        st.subheader("综述规格")
        col1, col2 = st.columns(2)
        col1.metric("综述标题", spec.review_title)
        col2.metric("语言", spec.language)

        st.write("**核心实体**：" + "；".join(spec.core_entities))
        st.write("**证据类型**：" + "；".join(spec.evidence_types))
        st.write("**时间范围**：" + (spec.time_range or "未指定"))

        st.subheader("章节结构")
        for s in spec.sections:
            with st.expander(f"{s.number}. {s.title}", expanded=True):
                st.write(f"**焦点**：{s.focus}")
                st.write("**关键问题**：")
                for q in s.key_questions:
                    st.write(f"- {q}")

# ==================== Tab 2 ====================
with tab2:
    st.header("Step 2：双源检索（PubMed + ClinicalTrials）")

    if not st.session_state.spec:
        st.info("请先完成 Step 1")
    else:
        if st.button("执行检索", type="primary", key="btn_search"):
            with st.spinner("检索中，请稍候..."):
                results = run_search(st.session_state.spec)
                st.session_state.search_summary = results
            st.success("检索完成")

        if st.session_state.search_summary:
            results = st.session_state.search_summary
            total = sum(r.get("count", 0) for r in results.values())
            st.metric("总检索条数", total)

            for tid, r in results.items():
                db = r.get("database", "?")
                cnt = r.get("count", 0)
                with st.expander(f"[{db}] {tid} — {cnt} 条"):
                    st.write(f"**目的**：{r.get('purpose', '')}")
                    st.code(r.get("keywords", ""), language=None)
                    if r.get("records"):
                        st.write("**示例结果**：")
                        for rec in r["records"][:3]:
                            st.write(f"- {rec.get('title', '')[:120]}")

# ==================== Tab 3 ====================
with tab3:
    st.header("Step 3：信息提取")
    st.caption("对每条源用 LLM 提取结构化信息并归类到章节")

    if not st.session_state.spec:
        st.info("请先完成 Step 1")
    else:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) AS n FROM sources s
            LEFT JOIN extracted_info e ON s.source_id = e.source_id
            WHERE e.source_id IS NULL AND s.source_id LIKE 'pubmed_%'
        """)
        pending = cur.fetchone()["n"]
        conn.close()

        st.info(f"待提取 PubMed 记录：**{pending}** 条")

        if st.button("开始批量提取", type="primary", key="btn_extract", disabled=(pending == 0)):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT s.source_id FROM sources s
                LEFT JOIN extracted_info e ON s.source_id = e.source_id
                WHERE e.source_id IS NULL AND s.source_id LIKE 'pubmed_%'
                ORDER BY s.source_id
            """)
            ids = [r["source_id"] for r in cur.fetchall()]
            conn.close()

            progress = st.progress(0)
            status = st.empty()
            success = 0
            for i, sid in enumerate(ids):
                status.write(f"[{i+1}/{len(ids)}] {sid}")
                try:
                    result = extract_and_save(sid)
                    if "error" not in result:
                        success += 1
                except Exception as e:
                    status.write(f"  FAILED: {e}")
                progress.progress((i + 1) / len(ids))
            status.write(f"完成：{success}/{len(ids)}")

        # 统计
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT extracted_json FROM extracted_info")
        rows = cur.fetchall()
        conn.close()

        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for row in rows:
            try:
                ex = json.loads(row["extracted_json"])
                for s in ex.get("relevant_sections", []) or []:
                    try:
                        k = int(s)
                        if k in counts:
                            counts[k] += 1
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass

        st.divider()
        st.subheader("已提取统计")
        cols = st.columns(4)
        for i in range(1, 5):
            cols[i-1].metric(f"Section {i}", counts[i])

# ==================== Tab 4 ====================
with tab4:
    st.header("Step 4：生成大纲")

    if not st.session_state.spec:
        st.info("请先完成 Step 1")
    else:
        if st.button("生成大纲", type="primary", key="btn_outline"):
            with st.spinner("生成中..."):
                outline = generate_outline(st.session_state.spec)
                st.session_state.outline = outline
            st.success("完成")

        if st.session_state.outline:
            for sec in st.session_state.outline["sections"]:
                with st.expander(
                    f"第 {sec['section_number']} 节：{sec['title']} "
                    f"（{len(sec.get('supporting_sources', []))} 源 / {sec.get('estimated_words', 0)} 字）",
                    expanded=True
                ):
                    st.write(f"**中心论点**：{sec.get('thesis', '')}")
                    st.write("**要点**：")
                    for kp in sec.get("key_points", []):
                        st.write(f"- {kp}")
                    if sec.get("notes"):
                        st.info(sec["notes"])

# ==================== Tab 5 ====================
with tab5:
    st.header("Step 5：分节写作")
    st.caption("依次写作 4 节，可能耗时 5-10 分钟")

    if not st.session_state.outline:
        st.info("请先完成 Step 4")
    else:
        if st.button("开始写作", type="primary", key="btn_write"):
            with st.spinner("写作中..."):
                result = write_all()
                st.session_state.drafts = {
                    k: v for k, v in result.items() if "content" in v
                }
            st.success("写作完成")

        if st.session_state.drafts:
            for k in sorted(st.session_state.drafts.keys()):
                v = st.session_state.drafts[k]
                with st.expander(
                    f"第 {k} 节：{v.get('title', '')}（{v.get('char_count', 0)} 字）",
                    expanded=(k == 1)
                ):
                    st.markdown(v.get("content", ""))

# ==================== Tab 6 ====================
with tab6:
    st.header("Step 6：引用核查")

    if not st.session_state.drafts:
        st.info("请先完成 Step 5")
    else:
        if st.button("开始核查", type="primary", key="btn_verify"):
            with st.spinner("核查中..."):
                results = {}
                for k, v in st.session_state.drafts.items():
                    if "content" in v:
                        results[k] = verify_draft(v["content"], k)
                st.session_state.verify_results = results
            st.success("核查完成")

        if st.session_state.verify_results:
            cols = st.columns(4)
            for i, (k, r) in enumerate(sorted(st.session_state.verify_results.items())):
                rate = r.get("support_rate_strict", 0)
                cols[i % 4].metric(
                    f"Section {k}",
                    f"{rate:.1%}",
                    delta=f"{r.get('supported', 0)}/{r.get('sentences_needing_citation', 0)}",
                )

            st.divider()
            for k, r in sorted(st.session_state.verify_results.items()):
                bad = [d for d in r.get("details", [])
                       if d["verdict"] in ("unsupported", "partially_supported", "uncited")]
                if bad:
                    with st.expander(f"Section {k} — {len(bad)} 条需关注"):
                        for d in bad:
                            st.warning(f"[{d['verdict']}] {d['sentence'][:180]}")
                            if d.get("reason"):
                                st.caption(d["reason"])

# ==================== Tab 7 ====================
with tab7:
    st.header("Step 7：组装综述")

    if not st.session_state.drafts:
        st.info("请先完成 Step 5")
    else:
        if st.button("生成完整综述", type="primary", key="btn_assemble"):
            with st.spinner("组装中..."):
                try:
                    markdown = assemble()
                    st.session_state.final_markdown = markdown
                except Exception as e:
                    st.error(f"组装失败：{e}")
            st.success("完成")

        if st.session_state.final_markdown:
            st.download_button(
                "下载 Markdown",
                data=st.session_state.final_markdown.encode("utf-8"),
                file_name=f"review_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                mime="text/markdown",
                use_container_width=True,
            )

            st.divider()
            with st.expander("预览", expanded=True):
                st.markdown(st.session_state.final_markdown)