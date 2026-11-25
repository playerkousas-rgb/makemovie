# Spec 014 - 笔触 #2

## 规则 Rules
- 版本 B 使用原生 320x180 1px 整数像素画布，4x NEAREST 无损放大至 1280x720
- 严格执行双风格同镜头同步规范（Treatment 1：深夜小确幸・经典中景推镜）

## 参数 Parameters
pixel_native_width: 320
pixel_native_height: 180
pixel_upscale: 4
pixel_resample: NEAREST

## 正例 / 反例
- 正例：严格遵循上述参数由纯 Python + PIL 代码程序化生成，画面干净、结构准确
- 反例：凭想象随意用色、使用 #000000 纯黑描边、平滑数码渐变或将文字画入底图

## 检查清单 QA
- [x] 有无违反规则？（已纳入自动化与缩图 Self-Review）
- [x] 有无走样 / 变色？（色板与几何骨骼锁定）
