# 🤖 gdl-agent

**AI Agent for automated ArchiCAD GDL library object development.**

> Turn natural language instructions into compiled `.gsm` library parts — automatically.

```
$ gdl-agent run "给窗户加一个百叶窗选项，参数名 bSunshade，3D 用 PRISM_ 生成"

  🚀 GDL Agent
     Task: 给窗户加一个百叶窗选项...
     File: src/window.xml
     Max retries: 5

  ─── Attempt 1/5 ───
  🧠 Calling LLM...
  ✓ Validation passed
  🔧 Compiling...
  ✗ Compile error: Mismatched IF/ENDIF (IF: 1, ENDIF: 0)

  ─── Attempt 2/5 ───
  🧠 Calling LLM...
  ✓ Validation passed
  🔧 Compiling...
  ✅ Compiled! (320ms)

  ┌─ Result ─────────────────────────────────────────┐
  │ ✅ Compiled successfully in 2 attempt(s)          │
  │    Output: output/window.gsm                      │
  │    Tokens: 2,847 | Time: 4,120ms                  │
  └──────────────────────────────────────────────────┘
```

## What is this?

`gdl-agent` is an **agentic AI tool** that writes, compiles, and debugs [GDL](https://gdl.graphisoft.com/) (Geometric Description Language) code for ArchiCAD library objects. Unlike Copilot-style tools that suggest code for you to accept, this agent operates autonomously:

1. **Reads** your XML source file
2. **Generates** GDL code via LLM (GLM-4, Claude, GPT-4, DeepSeek, or local Ollama models)
3. **Writes** the code to disk
4. **Compiles** using ArchiCAD's `LP_XMLConverter`
5. **Analyzes** errors and **retries** automatically (up to N times)
6. **Reports** success or failure with full execution history

## Prerequisites

- **Python 3.10+**
- **ArchiCAD** installed (provides `LP_XMLConverter`)
- **LLM API key** from any supported provider (or a local model via Ollama)

## Quick Start

```bash
# Install
pip install gdl-agent

# Initialize workspace
cd my-gdl-project
gdl-agent init

# Set your API key
export ZHIPU_API_KEY="your-key-here"  # or ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.

# Run a task
gdl-agent run "Create a parametric door with width A, height B, and a glass panel option"
```

## Installation

### From PyPI (when published)

```bash
pip install gdl-agent
```

### From source

```bash
git clone https://github.com/byewind/gdl-agent.git
cd gdl-agent
pip install -e ".[dev]"
```

### For local model support

```bash
pip install gdl-agent[local]  # adds ollama package
```

## Configuration

After running `gdl-agent init`, edit `config.toml`:

```toml
[llm]
model = "glm-4-flash"            # or "claude-sonnet-4-5-20250929", "gpt-4o", "ollama/glm4:9b"
# api_key = "your-key"           # or set via environment variable
# api_base = "https://..."       # custom endpoint (for Zhipu, Ollama, etc.)
temperature = 0.2
max_tokens = 4096

[agent]
max_iterations = 5               # max retry attempts
validate_xml = true               # pre-compile XML validation
diff_check = true                 # stop if LLM produces identical code twice
auto_version = true               # add version suffix to output files

[compiler]
# path = "/path/to/LP_XMLConverter"  # auto-detected if on PATH
timeout = 60
```

### Model Selection Guide

| Task Complexity | Recommended Model | Cost | When to Use |
|:---|:---|:---:|:---|
| Simple | `glm-4-flash` | ≈ 0 | Modify parameter values, adjust dimensions |
| Medium | `glm-4-plus` | Low | Add parameters + logic |
| Complex | `claude-sonnet-4-5-20250929` | Medium | New objects, complex geometry |
| Extreme | `claude-opus-4-6` | High | Macro calls, nested subroutines |
| Offline | `ollama/glm4:9b` | Free | Privacy-sensitive, zero-cost development |

## Usage

### Single task

```bash
# Basic
gdl-agent run "Add a boolean parameter bSunshade to the window"

# Specify source file
gdl-agent run "Increase default width to 1200" --file src/window.xml

# Use a specific model
gdl-agent run "Create a complex curtain wall module" --model claude-sonnet-4-5-20250929

# Use local Ollama model
gdl-agent run "Fix the 2D symbol" --model ollama/glm4:9b

# Limit retries
gdl-agent run "Add louver geometry" --max-retries 3

# Test without ArchiCAD (mock compiler)
gdl-agent run "Create a test object" --mock
```

### Interactive mode

```bash
gdl-agent chat

🤖 GDL Agent Interactive Mode
Type your instructions. Use 'quit' or Ctrl+C to exit.

gdl-agent > Create a basic window object with width A and height B
  ✅ Compiled! → output/current.gsm

gdl-agent > Now add a sunshade option with 5 louver slats
  ✅ Compiled! → output/current.gsm

gdl-agent > Make the louver count adjustable via parameter iLouverCount
  ✅ Compiled! → output/current.gsm
```

### Other commands

```bash
gdl-agent init              # Initialize workspace
gdl-agent show-config       # Display current configuration
```

## Project Structure

```
my-gdl-project/
├── config.toml             # Agent configuration
├── prompts/
│   └── system.md           # LLM role definition (customizable)
├── knowledge/              # RAG knowledge base
│   ├── GDL_Reference_Guide.md
│   ├── XML_Template.md
│   └── Common_Errors.md
├── templates/              # Seed templates (gsm → xml)
├── src/                    # Working XML source files
└── output/                 # Compiled .gsm files
```

## Architecture

```
┌─ Human ─────────┐
│ Natural language │
│ instructions     │
└────────┬─────────┘
         ▼
┌─ Agent (core.py) ─────────────────────┐
│                                        │
│  ┌─ LLM (llm.py) ──────────────────┐  │
│  │ GLM-4 / Claude / GPT / Ollama   │  │
│  │ + RAG knowledge injection        │  │
│  └──────────────────────────────────┘  │
│           │                            │
│           ▼                            │
│  ┌─ XML Utils ──────────────────────┐  │
│  │ Validate → Write → Diff check   │  │
│  └──────────────────────────────────┘  │
│           │                            │
│           ▼                            │
│  ┌─ Compiler (compiler.py) ─────────┐  │
│  │ LP_XMLConverter xml2libpart      │  │
│  └──────────────────────────────────┘  │
│           │                            │
│           ▼                            │
│  ┌─ Feedback Loop ──────────────────┐  │
│  │ Success → Report                 │  │
│  │ Failure → Error → LLM → Retry   │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```

## Advanced Usage

### Custom Knowledge Base

Add your own `.md` files to `knowledge/` to teach the agent about your specific patterns:

```bash
# Add your firm's GDL coding standards
cp my-gdl-standards.md knowledge/

# Add ArchiCAD version-specific notes
cp ac28-migration-notes.md knowledge/
```

### Batch Processing

```bash
# Process multiple files with a shell loop
for f in src/*.xml; do
    gdl-agent run "Update material parameter to use Surface type" --file "$f"
done
```

### Fine-tuning (Advanced)

Prepare training data from your existing library:

```bash
# Decompile all .gsm files to XML
for f in my-library/*.gsm; do
    LP_XMLConverter libpart2xml "$f" "training-data/$(basename "$f" .gsm)/"
done

# Then fine-tune GLM-4-9B with these examples
# (See Ollama/vLLM documentation for fine-tuning instructions)
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=gdl_agent

# Lint
ruff check .
```

## Safety Features

- **Max iterations**: Prevents infinite retry loops (default: 5)
- **Diff detection**: Stops if the LLM produces identical code twice
- **XML pre-validation**: Catches malformed XML before calling the compiler
- **GDL structure checks**: Validates IF/ENDIF, FOR/NEXT matching
- **Timeout**: Compiler calls have a configurable timeout (default: 60s)
- **Auto-versioning**: Output files get version suffixes to prevent overwrites

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- [Graphisoft](https://graphisoft.com/) for ArchiCAD and LP_XMLConverter
- [litellm](https://github.com/BerriAI/litellm) for unified LLM API access
- The GDL community for decades of parametric design knowledge
