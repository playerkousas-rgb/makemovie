# Spec 093 - 输出质检 #8

## 规则 Rules
- QA 必检项 6：验证修改 src/main.py 第一行 SUBTITLE_LINE 时直接命中底片缓存，耗时低于 3 秒
- 严格执行双风格同镜头同步规范（Treatment 1：深夜小确幸・经典中景推镜）

## 参数 Parameters
qa_check_fast_subtitle_swap: true

## 正例 / 反例
- 正例：严格遵循上述参数由纯 Python + PIL 代码程序化生成，画面干净、结构准确
- 反例：凭想象随意用色、使用 #000000 纯黑描边、平滑数码渐变或将文字画入底图

## 检查清单 QA
- [x] 有无违反规则？（已纳入自动化与缩图 Self-Review）
- [x] 有无走样 / 变色？（色板与几何骨骼锁定）
