# GDL Agent 测试程序部署指南

## 🎯 核心问题：测试程序应该放在哪里？

答案取决于**使用场景**。有3种部署方式：

---

## 📁 方案A：独立发布（推荐 ⭐⭐⭐⭐⭐）

### **位置结构**
```
你的GitHub仓库:
├── gdl-agent/                    # 主项目（开发者看的）
│   ├── src/
│   │   └── gdl_agent/
│   ├── tests/                    # 开发者的pytest测试
│   ├── README.md
│   └── ...
│
└── releases/                     # 发布包（建筑师下载的）
    ├── windows/
    │   └── test_gdl_simple.py
    └── macos/
        ├── GDL测试工具.command
        ├── test_gdl_simple.py
        └── README_macOS.txt
```

### **实际操作**

#### 选项1：作为GitHub Release附件
```bash
# 你在本地打包
./build_macos_release.sh

# 在GitHub上创建Release
# 把生成的ZIP上传为附件

# 用户下载路径：
# https://github.com/byewind/gdl-agent/releases/download/v1.0/GDL-Agent-Tester-macOS-1.0.zip
```

**README.md 中写**：
```markdown
## 快速测试

### Windows用户
下载 [test_gdl_simple.py](链接)，双击运行

### macOS用户  
下载 [GDL-Agent-Tester-macOS.zip](链接)，解压后双击.command文件

不需要安装gdl-agent包，这是独立的测试工具。
```

**优点**：
- ✅ 建筑师不需要克隆整个仓库
- ✅ 不需要安装依赖
- ✅ 文件小（<20KB vs 整个项目>1MB）
- ✅ 下载快

**缺点**：
- ❌ 需要手动维护Release版本
- ❌ 代码更新后要重新发布

---

## 📁 方案B：嵌入主项目（适合进阶用户 ⭐⭐⭐）

### **位置结构**
```
gdl-agent/
├── src/
│   └── gdl_agent/               # 核心代码
│       ├── __init__.py
│       ├── core.py
│       ├── compiler.py
│       └── xml_handler.py
│
├── tests/                       # 开发者的自动化测试
│   ├── test_core.py
│   └── test_compiler.py
│
├── playground/                  # 🎨 用户测试区（新增）
│   ├── README.md               # "如何使用测试工具"
│   ├── test_gdl_simple.py      # 通用测试脚本
│   ├── GDL测试工具.command      # macOS启动器
│   └── examples/               # 示例GDL文件
│       ├── simple_box.xml
│       └── parametric_window.xml
│
├── README.md
└── pyproject.toml
```

### **实际操作**

**README.md 主文档**：
```markdown
## 安装

### 开发者（想参与开发）
```bash
git clone https://github.com/byewind/gdl-agent.git
cd gdl-agent
pip install -e .
```

### 建筑师（只想测试）
```bash
git clone https://github.com/byewind/gdl-agent.git
cd gdl-agent/playground

# Windows:
python test_gdl_simple.py

# macOS:
./GDL测试工具.command
```

或者直接下载 `playground` 文件夹即可。
```

**playground/README.md**：
```markdown
# GDL Agent 测试工具

这个文件夹包含用户友好的测试工具，不需要安装gdl-agent包。

## 快速开始

### Windows
双击 `test_gdl_simple.py`

### macOS
双击 `GDL测试工具.command`

## 文件说明
- `test_gdl_simple.py` - 核心测试程序
- `GDL测试工具.command` - macOS启动器
- `examples/` - 示例GDL文件
```

**优点**：
- ✅ 用户可以 `git pull` 更新
- ✅ 代码和测试工具在同一个仓库
- ✅ 容易维护（改一次就同步）

**缺点**：
- ❌ 用户需要克隆整个仓库
- ❌ 不懂Git的建筑师可能困惑

---

## 📁 方案C：混合方案（最灵活 ⭐⭐⭐⭐⭐ 强烈推荐）

结合A和B的优点：

### **项目结构**
```
gdl-agent/
├── src/gdl_agent/              # 核心代码
├── tests/                      # pytest测试（开发者用）
├── tools/                      # 🔧 用户工具（新增）
│   └── standalone-tester/      # 独立测试器
│       ├── README.md
│       ├── build.sh            # 打包脚本
│       ├── test_gdl_simple.py
│       └── macos/
│           ├── GDL测试工具.command
│           └── README_macOS.txt
│
├── README.md
└── .github/
    └── workflows/
        └── release.yml         # 自动发布
```

### **工作流程**

#### 1. 开发阶段
```bash
# 你在 tools/standalone-tester/ 目录工作
cd tools/standalone-tester
vim test_gdl_simple.py  # 改进测试工具
```

#### 2. 测试阶段
```bash
# 本地测试
python test_gdl_simple.py

# 打包测试
./build.sh
# 生成 releases/GDL-Agent-Tester-*.zip
```

#### 3. 发布阶段（自动化）

**创建 `.github/workflows/release.yml`**：
```yaml
name: Release Tester

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build macOS package
        run: |
          cd tools/standalone-tester
          chmod +x build.sh
          ./build.sh
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            tools/standalone-tester/releases/*.zip
            tools/standalone-tester/releases/*.sha256
```

**使用**：
```bash
# 你只需打tag
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions自动：
# 1. 运行build.sh
# 2. 创建Release
# 3. 上传ZIP文件
```

#### 4. 用户下载

**README.md 主文档**：
```markdown
## 快速测试（不需要安装）

直接下载测试工具：
- [Windows版](https://github.com/byewind/gdl-agent/releases/latest/download/test_gdl_simple.py)
- [macOS版](https://github.com/byewind/gdl-agent/releases/latest/download/GDL-Agent-Tester-macOS.zip)

双击运行即可，无需安装任何依赖。

## 开发者安装

如果你想参与开发：
```bash
git clone https://github.com/byewind/gdl-agent.git
pip install -e .
pytest tests/
```
```

**优点**：
- ✅ 代码在仓库里（容易维护）
- ✅ 自动发布（push tag就行）
- ✅ 用户体验最好（直接下载ZIP）
- ✅ 分离关注点（开发者看 src/，用户下载 Release）

**缺点**：
- ❌ 需要配置GitHub Actions（但只配一次）

---

## 🎯 具体推荐

### **如果你的项目现在是这样**：

```
gdl-agent/
├── gdl_agent/
│   ├── __init__.py
│   ├── core.py
│   └── compiler.py
├── README.md
└── pyproject.toml
```

### **建议修改为**（方案C）：

```bash
# 1. 创建工具目录
mkdir -p tools/standalone-tester/macos

# 2. 移动测试文件
mv test_gdl_simple.py tools/standalone-tester/
mv GDL测试工具.command tools/standalone-tester/macos/
mv README_macOS.txt tools/standalone-tester/macos/
mv build_macos_release.sh tools/standalone-tester/

# 3. 创建工具说明
cat > tools/standalone-tester/README.md << 'EOF'
# GDL Agent 独立测试工具

这个目录包含用户友好的测试工具，可以独立分发。

## 打包发布

```bash
./build_macos_release.sh
# 生成 releases/ 目录
```

## 手动测试

```bash
# Windows
python test_gdl_simple.py

# macOS
cd macos && ./GDL测试工具.command
```

## 自动发布

推送git tag即可自动发布：
```bash
git tag v1.0.0
git push origin v1.0.0
```
EOF

# 4. 提交
git add tools/
git commit -m "feat: add standalone tester tools"
git push
```

### **更新主README.md**：

```markdown
# GDL Agent

AI驱动的ArchiCAD参数化对象生成器

## 🚀 快速开始

### 只想测试？（建筑师）

下载独立测试工具，无需安装：
- **Windows**: [test_gdl_simple.py](https://github.com/byewind/gdl-agent/releases/latest/download/test_gdl_simple.py)
- **macOS**: [GDL-Agent-Tester-macOS.zip](https://github.com/byewind/gdl-agent/releases/latest/download/GDL-Agent-Tester-macOS.zip)

### 想要开发？（程序员）

```bash
git clone https://github.com/byewind/gdl-agent.git
cd gdl-agent
pip install -e .
```

详见[开发者文档](docs/DEVELOPMENT.md)

## 📖 文档

- [用户手册](docs/USER_GUIDE.md) - 建筑师看这个
- [API文档](docs/API.md) - 开发者看这个
- [测试工具说明](tools/standalone-tester/README.md)

## 🤝 贡献

欢迎贡献！请阅读[贡献指南](CONTRIBUTING.md)

## 📜 许可证

MIT License
```

---

## 📊 三种方案对比总结

| 方案 | 适用场景 | 用户体验 | 维护成本 | 推荐度 |
|------|---------|----------|----------|--------|
| **A. 独立发布** | 项目早期，用户少 | ⭐⭐⭐⭐ | ⭐⭐ 需手动更新 | ⭐⭐⭐ |
| **B. 嵌入项目** | 用户都懂Git | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **C. 混合方案** | 项目成熟，用户多样 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎯 立即行动建议

### **今天（最简单）**

使用**方案A**：
```bash
# 1. 在GitHub创建Release
# 2. 手动上传这些文件：
#    - test_gdl_simple.py
#    - GDL-Agent-Tester-macOS.zip

# 3. 在README中添加下载链接
```

### **本周（标准做法）**

迁移到**方案C**：
```bash
# 1. 创建 tools/standalone-tester/ 目录
# 2. 移动测试文件进去
# 3. 配置GitHub Actions自动发布
# 4. 打tag测试自动发布流程
```

### **未来（锦上添花）**

添加更多工具：
```
tools/
├── standalone-tester/    # 已有
├── gdl-converter/        # GDL格式转换工具
├── archicad-launcher/    # ArchiCAD快速启动工具
└── template-generator/   # GDL模板生成器
```

---

## 💡 关键原则

1. **分离关注点**
   - `src/` = 开发者关心的
   - `tools/` = 用户使用的
   - `tests/` = 自动化测试的

2. **降低门槛**
   - 用户不需要看到 `pytest`, `pip install`
   - 用户只需要：下载 → 双击 → 完成

3. **自动化一切**
   - 打tag → 自动打包 → 自动发布
   - 你只需要专注写代码

4. **文档清晰**
   - README主文档：2分钟能看懂
   - 进阶文档：放在 docs/ 目录

---

## 🎓 总结

**最佳实践**：

```
gdl-agent/
├── src/                  # 核心代码（开发者）
├── tests/                # 自动化测试（pytest）
├── tools/                # 用户工具（建筑师）
│   └── standalone-tester/
├── docs/                 # 文档
└── README.md            # 2分钟快速开始
```

**用户路径**：
```
GitHub Release页面 → 下载ZIP → 双击 → 测试
```

**开发者路径**：
```
git clone → pip install -e . → pytest → 改代码 → git push
```

**维护路径**：
```
改代码 → git commit → git tag v1.x → git push --tags → 自动发布
```

这就是**现代开源项目的标准结构**！
