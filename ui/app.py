"""
gdl-agent Web UI — Streamlit interface for architects.

Run: streamlit run ui/app.py
"""

import sys
import re
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from gdl_agent.hsf_project import HSFProject, ScriptType, GDLParameter
from gdl_agent.gdl_parser import parse_gdl_source, parse_gdl_file
from gdl_agent.paramlist_builder import build_paramlist_xml, validate_paramlist
from gdl_agent.compiler import MockHSFCompiler, HSFCompiler, CompileResult
from gdl_agent.core import GDLAgent, Status
from gdl_agent.knowledge import KnowledgeBase
from gdl_agent.skills_loader import SkillsLoader


# ── Page Config ───────────────────────────────────────────

st.set_page_config(
    page_title="gdl-agent",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Noto+Sans+SC:wght@300;400;600&display=swap');

.stApp { font-family: 'Noto Sans SC', sans-serif; }
code, .stCodeBlock { font-family: 'JetBrains Mono', monospace !important; }

.main-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem; font-weight: 600;
    background: linear-gradient(135deg, #22d3ee, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.sub-header { color: #94a3b8; font-size: 0.9rem; margin-top: -0.5rem; margin-bottom: 2rem; }

.welcome-card {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 2rem;
    margin: 1rem 0;
}
.step-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 1rem;
    padding: 0.75rem;
    background: #1e293b;
    border-radius: 8px;
    border-left: 3px solid #22d3ee;
}
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────

if "project" not in st.session_state:
    st.session_state.project = None
if "compile_log" not in st.session_state:
    st.session_state.compile_log = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "work_dir" not in st.session_state:
    st.session_state.work_dir = str(Path.home() / "gdl-agent-workspace")
if "agent_running" not in st.session_state:
    st.session_state.agent_running = False
if "model_api_keys" not in st.session_state:
    # Per-model API Key storage — pre-fill from config.toml provider_keys
    st.session_state.model_api_keys = {}


# ── Load config.toml defaults ──────────────────────────

_config_defaults = {}
_provider_keys: dict = {}   # {provider: api_key}

try:
    from gdl_agent.config import GDLAgentConfig
    import sys as _sys, os as _os
    # Load raw TOML to get provider_keys nested table
    if _sys.version_info >= (3, 11):
        import tomllib as _tomllib
    else:
        import tomli as _tomllib   # type: ignore

    _toml_path = _os.path.join(_os.path.dirname(__file__), "..", "config.toml")
    if _os.path.exists(_toml_path):
        with open(_toml_path, "rb") as _f:
            _raw = _tomllib.load(_f)
        _provider_keys = _raw.get("llm", {}).get("provider_keys", {})

    _config = GDLAgentConfig.load()
    _config_defaults = {
        "llm_model": _config.llm.model,
        "compiler_path": _config.compiler.path or "",
    }
except Exception:
    pass


def _key_for_model(model: str) -> str:
    """Pick the right API Key from provider_keys based on model name."""
    m = model.lower()
    if "glm" in m:
        return _provider_keys.get("zhipu", "")
    elif "deepseek" in m and "ollama" not in m:
        return _provider_keys.get("deepseek", "")
    elif "claude" in m:
        return _provider_keys.get("anthropic", "")
    elif "gpt" in m or "o3" in m or "o1" in m:
        return _provider_keys.get("openai", "")
    elif "gemini" in m:
        return _provider_keys.get("google", "")
    return ""

# ── Sidebar Config ────────────────────────────────────────

with st.sidebar:
    st.markdown('<p class="main-header">gdl-agent</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">v0.4.1 · HSF-native · AI-powered</p>', unsafe_allow_html=True)
    st.divider()

    st.subheader("📁 工作目录")
    work_dir = st.text_input("Work Directory", value=st.session_state.work_dir, label_visibility="collapsed")
    st.session_state.work_dir = work_dir

    st.divider()
    st.subheader("🔧 编译器 / Compiler")

    compiler_mode = st.radio(
        "编译模式",
        ["Mock (无需 ArchiCAD)", "LP_XMLConverter (真实编译)"],
        index=1 if _config_defaults.get("compiler_path") else 0,
    )

    converter_path = ""
    if compiler_mode.startswith("LP"):
        converter_path = st.text_input(
            "LP_XMLConverter 路径",
            value=_config_defaults.get("compiler_path", ""),
            placeholder="/Applications/GRAPHISOFT/ArchiCAD 28/LP_XMLConverter",
        )

    st.divider()
    st.subheader("🧠 AI 模型 / LLM")

    model_options = [
        # ── Anthropic Claude ──
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-5-20250918",
        "claude-opus-4-6",
        # ── 智谱 GLM (Z.ai) ──
        "glm-4.7",
        "glm-4.7-flash",
        "glm-4-plus",
        "glm-4-flash",
        # ── OpenAI ──
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
        # ── DeepSeek ──
        "deepseek-chat",
        "deepseek-reasoner",
        # ── Google Gemini ──
        "gemini/gemini-2.5-flash",
        "gemini/gemini-2.5-pro",
        # ── Ollama 本地 ──
        "ollama/qwen2.5:14b",
        "ollama/qwen3:8b",
        "ollama/deepseek-coder-v2:16b",
    ]

    default_model = _config_defaults.get("llm_model", "glm-4.7")
    default_index = model_options.index(default_model) if default_model in model_options else 4

    model_name = st.selectbox("模型 / Model", model_options, index=default_index)

    # Load or initialize API Key for this specific model
    if model_name not in st.session_state.model_api_keys:
        # Auto-fill from config.toml provider_keys
        st.session_state.model_api_keys[model_name] = _key_for_model(model_name)

    api_key = st.text_input(
        "API Key",
        value=st.session_state.model_api_keys.get(model_name, ""),
        type="password",
        help="Ollama 本地模式不需要 Key"
    )

    # Auto-save API Key if user manually edited it
    if api_key != st.session_state.model_api_keys.get(model_name, ""):
        st.session_state.model_api_keys[model_name] = api_key

    if "claude" in model_name:
        st.caption("🔑 [获取 Claude API Key →](https://console.anthropic.com/settings/keys)")
        st.caption("⚠️ API Key 需单独充值，与 Claude Pro 订阅额度无关")
    elif "glm" in model_name:
        st.caption("🔑 [获取智谱 API Key →](https://bigmodel.cn/usercenter/apikeys)")
    elif "gpt" in model_name or "o3" in model_name:
        st.caption("🔑 [获取 OpenAI API Key →](https://platform.openai.com/api-keys)")
    elif "deepseek" in model_name and "ollama" not in model_name:
        st.caption("🔑 [获取 DeepSeek API Key →](https://platform.deepseek.com/api_keys)")
    elif "gemini" in model_name:
        st.caption("🔑 [获取 Gemini API Key →](https://aistudio.google.com/apikey)")
    elif "ollama" in model_name:
        st.caption("🖥️ 本地运行，无需 Key。确保 Ollama 已启动。")

    # API Base URL — only needed for OpenAI-compatible custom endpoints
    # zai/ (GLM), deepseek/, anthropic/ are native LiteLLM providers, no api_base needed
    def _get_default_api_base(model: str) -> str:
        m = model.lower()
        if "ollama" in m:
            return "http://localhost:11434"
        # GLM uses zai/ native provider — no api_base
        # DeepSeek uses deepseek/ native provider — no api_base
        return ""

    default_api_base = _get_default_api_base(model_name)
    api_base = ""
    if default_api_base:
        api_base = st.text_input("API Base URL", value=default_api_base)

    max_retries = st.slider("最大重试次数", 1, 10, 5)

    st.divider()

    # Project info + quick reset
    if st.session_state.project:
        proj = st.session_state.project
        st.subheader(f"📦 {proj.name}")
        st.caption(f"参数: {len(proj.parameters)} | 脚本: {len(proj.scripts)}")
        if st.button("🗑️ 清除项目", use_container_width=True):
            st.session_state.project = None
            st.session_state.chat_history = []
            st.rerun()


# ── Helper Functions ──────────────────────────────────────

def get_compiler():
    if compiler_mode.startswith("Mock"):
        return MockHSFCompiler()
    return HSFCompiler(converter_path or None)

def get_llm():
    from gdl_agent.config import LLMConfig
    from gdl_agent.llm import LLMAdapter
    config = LLMConfig(
        model=model_name,
        api_key=api_key,
        api_base=api_base,
        temperature=0.2,
        max_tokens=4096,
    )
    return LLMAdapter(config)

def load_knowledge(task_type: str = "all"):
    kb_dir = Path(st.session_state.work_dir) / "knowledge"
    if not kb_dir.exists():
        kb_dir = Path(__file__).parent.parent / "knowledge"
    kb = KnowledgeBase(str(kb_dir))
    kb.load()
    return kb.get_by_task_type(task_type)

def load_skills():
    sk_dir = Path(st.session_state.work_dir) / "skills"
    if not sk_dir.exists():
        sk_dir = Path(__file__).parent.parent / "skills"
    sl = SkillsLoader(str(sk_dir))
    sl.load()
    return sl

def _versioned_gsm_path(proj_name: str, work_dir: str) -> str:
    """
    Return next available versioned GSM path.
    MyShelf_v1.gsm → MyShelf_v2.gsm → ...
    Preserves all previous compilations.
    """
    out_dir = Path(work_dir) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    v = 1
    while (out_dir / f"{proj_name}_v{v}.gsm").exists():
        v += 1
    return str(out_dir / f"{proj_name}_v{v}.gsm")


def _extract_project_name_regex(text: str) -> str:
    """Regex fallback: only use when LLM is unavailable."""
    patterns = [
        r'named?\s+([A-Za-z][A-Za-z0-9_]{2,30})',
        r'called\s+([A-Za-z][A-Za-z0-9_]{2,30})',
        r'名为\s*([A-Za-z][A-Za-z0-9_]{2,30})',
        r'叫\s*([A-Za-z][A-Za-z0-9_]{2,30})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return "MyObject"


def _extract_project_name(text: str, llm=None) -> str:
    """
    Extract a valid GDL object name from user description.
    Uses LLM for Chinese/ambiguous input; falls back to regex.
    """
    if llm is not None:
        try:
            resp = llm.generate([
                {
                    "role": "system",
                    "content": (
                        "Extract a short English GDL library object name from the user description. "
                        "Rules: CamelCase, letters and digits only, 3-24 chars. "
                        "Good examples: Bookshelf, WallPanel, WindowFrame, DoorUnit, StairStep, ColumnBase. "
                        "Reply with ONLY the name — no explanation, no quotes."
                    ),
                },
                {"role": "user", "content": text},
            ], max_tokens=12, temperature=0)
            name = resp.content.strip().split()[0]  # take first word only
            if re.match(r'^[A-Za-z][A-Za-z0-9]{2,23}$', name):
                return name
        except Exception:
            pass
    return _extract_project_name_regex(text)


# ── Welcome / Onboarding Panel ────────────────────────────

def show_welcome():
    st.markdown("""
<div class="welcome-card">
<h2 style="color:#22d3ee; margin-top:0; font-family:'JetBrains Mono';">欢迎使用 gdl-agent 🏗️</h2>
<p style="color:#94a3b8;">用自然语言驱动 ArchiCAD GDL 对象的创建与编译。无需了解 GDL 语法，直接描述需求即可。</p>
</div>
""", unsafe_allow_html=True)

    st.markdown("#### 三步快速开始")

    st.info("**① 配置 API Key**  \n在左侧边栏选择 AI 模型，填入对应 API Key。免费的智谱 GLM 可直接使用。")
    st.info("**② 开始对话**  \n在底部输入框描述你想创建的 GDL 对象，例如：  \n「创建一个宽 600mm、深 400mm 的书架，带 iShelves 参数控制层数」")
    st.info("**③ 编译输出**  \nAI 生成代码后自动触发编译。真实编译需在侧边栏配置 LP_XMLConverter 路径。Mock 模式可验证结构，无需安装 ArchiCAD。")

    st.divider()

    st.markdown("#### 或者：导入已有 GDL 文件")
    uploaded_file = st.file_uploader(
        "拖入 .gdl 文件开始编辑",
        type=["gdl", "txt"],
        help="支持 AI 生成或手写的 GDL 源码",
        key="welcome_upload",
    )
    if uploaded_file:
        content = uploaded_file.read().decode("utf-8", errors="replace")
        name = Path(uploaded_file.name).stem
        try:
            project = parse_gdl_source(content, name)
            project.work_dir = Path(st.session_state.work_dir)
            project.root = project.work_dir / project.name
            st.session_state.project = project
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"✅ 已导入 `{project.name}` — {len(project.parameters)} 个参数，{len(project.scripts)} 个脚本。可以开始对话修改了。"
            })
            st.rerun()
        except Exception as e:
            st.error(f"❌ 导入失败: {e}")

    st.divider()
    st.caption("💡 提示：第一条消息无需创建项目，直接描述需求，AI 会自动初始化。")


# ── Intent Classification ─────────────────────────────────

_GDL_KEYWORDS = [
    "创建", "生成", "制作", "做一个", "建一个", "写一个",
    "修改", "更新", "添加", "删除", "调整", "优化",
    "书架", "柜子", "窗", "门", "墙", "楼梯", "桌", "椅",
    "参数", "parameter", "script", "gdl", "gsm", "hsf",
    "compile", "编译", "build", "create", "make", "add",
    "3d", "2d", "prism", "block", "sphere",
]

def _is_gdl_intent(text: str) -> bool:
    """Quick keyword check — if obvious GDL request, skip LLM classification."""
    t = text.lower()
    return any(kw in t for kw in _GDL_KEYWORDS)

def classify_intent(text: str, llm) -> str:
    """
    Return 'GDL' if user wants to create/modify GDL objects,
    otherwise 'CHAT' for casual conversation.
    """
    # Fast path: obvious keywords
    if _is_gdl_intent(text):
        return "GDL"

    # LLM-based classification for ambiguous cases
    try:
        resp = llm.generate([
            {
                "role": "system",
                "content": (
                    "You are an intent classifier for a GDL object builder app. "
                    "Reply with exactly one word: GDL or CHAT.\n"
                    "GDL = user wants to create, modify, compile, or ask technical questions about ArchiCAD GDL library objects.\n"
                    "CHAT = greeting, small talk, general questions about the app, or anything unrelated to GDL code generation."
                ),
            },
            {"role": "user", "content": text},
        ], max_tokens=5, temperature=0)
        result = resp.content.strip().upper()
        return "GDL" if "GDL" in result else "CHAT"
    except Exception:
        # If classification fails, default to CHAT (safer)
        return "CHAT"


def chat_respond(user_input: str, history: list, llm) -> str:
    """Simple conversational response without triggering Agent."""
    system_msg = {
        "role": "system",
        "content": (
            "你是 gdl-agent 的助手，专注于 ArchiCAD GDL 库构件的创建与编译。"
            "用户可以和你闲聊，也可以让你创建 GDL 对象。"
            "闲聊时自然回应，简洁友好；涉及 GDL 创建需求时提醒用户直接描述需求即可开始生成。"
            "回复使用中文，专业术语保留英文（GDL、HSF、ArchiCAD、paramlist 等）。"
        ),
    }
    messages = [system_msg]
    # Include recent history for context (last 6 messages)
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})

    try:
        resp = llm.generate(messages)
        return resp.content
    except Exception as e:
        return f"❌ {str(e)}"


# ── Run Agent (shared logic) ──────────────────────────────

def run_agent(user_input: str, proj: HSFProject, status_col):
    """Run agent and return response message string."""
    events = []

    status_ph = status_col.empty()
    detail_ph = status_col.empty()

    def on_event(event_type, data):
        events.append((event_type, data))
        if event_type == "analyze":
            scripts = data.get("affected_scripts", [])
            status_ph.info(f"🔍 分析中... 影响脚本: {', '.join(scripts)}")
        elif event_type == "attempt":
            status_ph.info(f"🧠 第 {data['attempt']} 次尝试，调用 AI...")
        elif event_type == "compile_start":
            status_ph.info("🔧 编译中...")
        elif event_type == "compile_error":
            detail_ph.warning(f"⚠️ 第 {data['attempt']} 次编译失败: {data['error'][:200]}")
        elif event_type == "success":
            status_ph.success(f"✅ 成功！第 {data['attempt']} 次尝试编译通过。")

    try:
        llm = get_llm()
        compiler = get_compiler()
        knowledge = load_knowledge()
        skills_loader = load_skills()
        skills_text = skills_loader.get_for_task(user_input)

        output_gsm = _versioned_gsm_path(proj.name, st.session_state.work_dir)

        agent = GDLAgent(
            llm=llm,
            compiler=compiler,
            max_iterations=max_retries,
            on_event=on_event,
        )

        result = agent.run(
            instruction=user_input,
            project=proj,
            output_gsm=output_gsm,
            knowledge=knowledge,
            skills=skills_text,
        )

        mock_tag = " [Mock]" if compiler_mode.startswith("Mock") else ""
        if result.status == Status.SUCCESS:
            msg = (
                f"✅ **编译成功{mock_tag}** — 第 {result.attempts} 次尝试\n\n"
                f"📦 输出: `{result.output_path}`\n\n"
                f"参数: {len(proj.parameters)} | "
                f"脚本: {', '.join(st_type.value for st_type in proj.scripts)}"
            )
            if compiler_mode.startswith("Mock"):
                msg += "\n\n⚠️ Mock 模式不生成真实 .gsm，切换到 LP_XMLConverter 进行真实编译。"
        elif result.status == Status.FAILED:
            msg = f"❌ **失败**: {result.error_summary}"
        elif result.status == Status.EXHAUSTED:
            msg = (
                f"⚠️ **{result.attempts} 次尝试后仍未成功**\n\n"
                f"最后错误: {result.error_summary[:300]}\n\n"
                f"建议: 换一种描述方式，或切换到「编辑」Tab 手动修改代码。"
            )
        else:
            msg = f"⛔ 任务被阻止: {result.error_summary}"

        status_ph.empty()
        detail_ph.empty()

        st.session_state.compile_log.append({
            "project": proj.name,
            "instruction": user_input,
            "success": result.status == Status.SUCCESS,
            "attempts": result.attempts,
            "message": result.error_summary or "Success",
        })

        return msg

    except Exception as e:
        status_ph.empty()
        detail_ph.empty()
        return f"❌ **错误**: {str(e)}"


# ══════════════════════════════════════════════════════════
#  Main Layout: Left Chat | Right Editor
# ══════════════════════════════════════════════════════════

col_chat, col_editor = st.columns([2, 3], gap="large")


# ── Left: Chat History ────────────────────────────────────

with col_chat:
    if not st.session_state.project:
        st.markdown("### 💬 开始创建")
        st.markdown(
            '<p style="color:#64748b; font-size:0.9rem;">在底部输入框描述你想创建的对象，AI 会自动生成并编译。</p>',
            unsafe_allow_html=True,
        )
    else:
        proj_now = st.session_state.project
        st.markdown(f"### 💬 {proj_now.name}")
        st.caption(f"参数: {len(proj_now.parameters)} | 脚本: {len(proj_now.scripts)}")

    # Chat history
    for msg in st.session_state.chat_history:
        st.chat_message(msg["role"]).markdown(msg["content"])

    # Placeholder for live agent output (populated when agent runs)
    live_output = st.empty()


# ── Right: Welcome / Project Editor ──────────────────────

with col_editor:
    if not st.session_state.project:
        show_welcome()
    else:
        proj_now = st.session_state.project

        tab_edit, tab_compile, tab_log = st.tabs(["📝 编辑", "🔧 编译", "📋 日志"])

        # ── Edit Tab ──────────────────────────────────────
        with tab_edit:
            st.markdown("#### 参数列表")
            param_data = [
                {
                    "Type": p.type_tag,
                    "Name": p.name,
                    "Value": p.value,
                    "Description": p.description,
                    "Fixed": "✓" if p.is_fixed else "",
                }
                for p in proj_now.parameters
            ]
            if param_data:
                st.dataframe(param_data, use_container_width=True, hide_index=True)
            else:
                st.caption("暂无参数，通过对话让 AI 添加，或手动添加。")

            with st.expander("➕ 手动添加参数"):
                pc1, pc2, pc3, pc4 = st.columns(4)
                with pc1:
                    p_type = st.selectbox("Type", [
                        "Length", "Integer", "Boolean", "RealNum", "Angle",
                        "String", "Material", "FillPattern", "LineType", "PenColor",
                    ])
                with pc2:
                    p_name = st.text_input("Name", value="bNewParam")
                with pc3:
                    p_value = st.text_input("Value", value="0")
                with pc4:
                    p_desc = st.text_input("Description")
                if st.button("添加参数"):
                    try:
                        proj_now.add_parameter(GDLParameter(p_name, p_type, p_desc, p_value))
                        st.success(f"✅ {p_type} {p_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            st.divider()
            st.markdown("#### 脚本")
            script_tabs = st.tabs(["3D", "2D", "Master", "Param", "UI", "Properties"])
            script_map = [
                (ScriptType.SCRIPT_3D, "3d.gdl"),
                (ScriptType.SCRIPT_2D, "2d.gdl"),
                (ScriptType.MASTER, "1d.gdl"),
                (ScriptType.PARAM, "vl.gdl"),
                (ScriptType.UI, "ui.gdl"),
                (ScriptType.PROPERTIES, "pr.gdl"),
            ]
            for tab, (stype, fname) in zip(script_tabs, script_map):
                with tab:
                    current = proj_now.get_script(stype)
                    new_content = st.text_area(
                        fname, value=current, height=280, key=f"script_{fname}",
                    )
                    if new_content != current:
                        proj_now.set_script(stype, new_content)

            if st.button("🔍 验证参数"):
                issues = validate_paramlist(proj_now.parameters)
                if issues:
                    for i in issues:
                        st.warning(i)
                else:
                    st.success("✅ 参数验证通过")

        # ── Compile Tab ───────────────────────────────────
        with tab_compile:
            # Auto versioned output path — no manual input needed
            next_gsm = _versioned_gsm_path(proj_now.name, st.session_state.work_dir)
            next_ver = Path(next_gsm).stem  # e.g. MyShelf_v2
            st.caption(f"📦 下次编译输出: `{Path(next_gsm).name}`")

            col_c, col_p = st.columns([1, 1])

            with col_c:
                if st.button("🔧 手动编译", type="primary"):
                    output_path = _versioned_gsm_path(proj_now.name, st.session_state.work_dir)

                    with st.spinner("写入 HSF..."):
                        try:
                            hsf_dir = proj_now.save_to_disk()
                        except Exception as e:
                            st.error(f"写入失败: {e}")
                            st.stop()

                    with st.spinner("编译中..."):
                        compiler = get_compiler()
                        result = compiler.hsf2libpart(str(hsf_dir), output_path)

                    if result.success:
                        if compiler_mode.startswith("Mock"):
                            st.success(
                                f"✅ **[Mock]** 结构验证通过！\n\n"
                                f"📁 HSF 目录: `{hsf_dir}`"
                            )
                        else:
                            st.success(f"✅ 编译成功！\n\n📦 `{output_path}`")
                    else:
                        st.error(f"❌ 编译失败\n\n```\n{result.stderr}\n```")

                    st.session_state.compile_log.append({
                        "project": proj_now.name,
                        "instruction": "(manual compile)",
                        "success": result.success,
                        "attempts": 1,
                        "message": result.stderr or "Success",
                    })

            with col_p:
                st.markdown("##### 预览")
                with st.expander("paramlist.xml"):
                    st.code(build_paramlist_xml(proj_now.parameters), language="xml")
                with st.expander("HSF 目录结构", expanded=True):
                    tree = [f"📁 {proj_now.name}/", "  ├── libpartdata.xml",
                            "  ├── paramlist.xml", "  ├── ancestry.xml", "  └── scripts/"]
                    for stype in ScriptType:
                        if stype in proj_now.scripts:
                            n = proj_now.scripts[stype].count("\n") + 1
                            tree.append(f"       ├── {stype.value} ({n} lines)")
                    st.code("\n".join(tree), language="text")

        # ── Log Tab ───────────────────────────────────────
        with tab_log:
            if not st.session_state.compile_log:
                st.info("暂无记录")
            else:
                for entry in reversed(st.session_state.compile_log):
                    icon = "✅" if entry["success"] else "❌"
                    instr = entry.get("instruction", "")
                    st.markdown(f"**{icon} {entry['project']}** — {instr}")
                    if entry.get("attempts", 0) > 1:
                        st.caption(f"尝试 {entry['attempts']} 次")
                    st.code(entry["message"], language="text")
                    st.divider()

            if st.button("清除日志"):
                st.session_state.compile_log = []
                st.rerun()


# ══════════════════════════════════════════════════════════
#  Chat Input — Always at Bottom
# ══════════════════════════════════════════════════════════

user_input = st.chat_input(
    "描述你想创建或修改的 GDL 对象，如「创建一个宽 600mm 的书架，iShelves 控制层数」"
)

if user_input:
    # Add user message to history
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # Check API key first
    if not api_key and "ollama" not in model_name:
        err = "❌ 请在左侧边栏填入 API Key 后再试。"
        st.session_state.chat_history.append({"role": "assistant", "content": err})
        st.rerun()
    else:
        llm_for_classify = get_llm()

        # ── Intent classification ──
        intent = classify_intent(user_input, llm_for_classify)

        with live_output.container():
            st.chat_message("user").markdown(user_input)
            with st.chat_message("assistant"):
                if intent == "CHAT":
                    # ── Casual conversation — no project creation, no agent ──
                    msg = chat_respond(
                        user_input,
                        st.session_state.chat_history[:-1],  # exclude the just-added user msg
                        llm_for_classify,
                    )
                    st.markdown(msg)

                else:
                    # ── GDL intent — create project if needed, then run agent ──
                    if not st.session_state.project:
                        proj_name = _extract_project_name(user_input, llm=llm_for_classify)
                        new_proj = HSFProject.create_new(proj_name, work_dir=st.session_state.work_dir)
                        st.session_state.project = new_proj
                        st.info(f"📁 已初始化项目 `{proj_name}`")

                    proj_current = st.session_state.project
                    msg = run_agent(user_input, proj_current, st.container())
                    st.markdown(msg)

        st.session_state.chat_history.append({"role": "assistant", "content": msg})
        st.rerun()


# ── Footer ────────────────────────────────────────────────
st.divider()
st.markdown(
    '<p style="text-align:center; color:#64748b; font-size:0.8rem;">'
    'gdl-agent v0.4.1 · HSF-native · '
    '<a href="https://github.com/byewind/gdl-agent">GitHub</a>'
    '</p>',
    unsafe_allow_html=True,
)
