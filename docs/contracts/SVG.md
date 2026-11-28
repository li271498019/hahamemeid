# 链上 SVG 与 tokenURI

状态：owner 已批准的设计。两个 TLD 用同一张底图。日期：2026-11-20。

名字 NFT 的 `tokenURI` 在读取时现拼，不把 SVG 存进每个 token。每个 token 只存 `label` 和 `tld`。图片里唯一随名字变化的是中间那一行 `{label}.{tld}` 的文字、字号和基线。

## 文件

| 文件 | 作用 |
| --- | --- |
| `assets/svg/svg-generator.py` | 已批准的参考生成器，函数 `svg(name, tld)` |
| `assets/svg/prefix.svgpart` | 静态前缀，到名字文本的 `y="` 为止 |
| `assets/svg/mid.svgpart` | `y` 和 `font-size` 之间的静态片段 |
| `assets/svg/name-open.svgpart` | 字号和名字文本之间的静态片段 |
| `assets/svg/suffix.svgpart` | 从名字 `</text>` 到 `</svg>` |
| `assets/svg/samples/*.svg` | 三张样例，字节必须与生成器一致 |
| `assets/svg/samples/*.png` | 单张渲染 |
| `assets/svg/preview.png` | 三张并排，白底，间距 20px，1540×500 |

四个 `*.svgpart` 没有末尾换行。拷进 Solidity 字符串时不要再加 `\n`。文件是 UTF-8。金币上的 `Ð` 是 U+00D0 LATIN CAPITAL LETTER ETH，UTF-8 为 `C3 90`，不是 ASCII `D`。

| 文件 | 字节数 | SHA-256 |
| --- | --- | --- |
| `prefix.svgpart` | 5332 | `6bfd60bb48abab846f752cddbbb4f1d786b9436eec2d5d099bbdc14d4eee5033` |
| `mid.svgpart` | 54 | `d3639713fe82b6cfdf16b8f91b8b82085cbcebe76348164d051963d6ceb460ba` |
| `name-open.svgpart` | 33 | `8f725fb3c6dda08a3808a210e4b76cc829cd42039a2d8ef4d7571b85fdd97087` |
| `suffix.svgpart` | 156 | `9e939574a89163960d6f2d47ed7a8eaea226f52e24c429d837d5f7f4277a1ec2` |
| `samples/a.haha.svg` | 5586 | `79fc84ca90f652a624e8572ff2c6dda731f079472e4770ff5b4b6fcbdd523136` |
| `samples/myagent.meme.svg` | 5592 | `bb4a674c268650774e2510d2a43d420c62e751dcc35a90e0f06784e765ee278a` |
| `samples/superlongagentname2026.haha.svg` | 5607 | `be9226d4b9720c644e3f666a1b6786ee6bd7d73e2ebfc05297943c78014bff43` |

## 画面

- 画布 500×500，`viewBox="0 0 500 500"`。
- 纵向渐变 `#FFC21A` → `#FF7A1A`。
- 顶部居中白色粗体 `haha.meme`，字号 30，Arial。
- 底部居中白色粗体 `agent id`，字号 24，`letter-spacing="2"`，`y="468"`。
- 底部一排半透明（`opacity="0.28"`）的手绘柴犬头、青蛙和金币（符号 `Ð`、`S`、`P`）。两个 TLD 完全一样。
- 中间是 `{label}.{tld}`，白色粗体 Arial，水平居中。

字号公式（与 `svg-generator.py` 相同）：

```text
n   = len(label) + len(tld) + 1
fsz = int(min(96, 420 / n / 0.58))
y   = round_half_even(250 + fsz * 0.35)
```

`int` 是向 0 截断。`y` 用 Python 格式化 `f"{value:.0f}"` 的半偶数舍入（banker's rounding），不是四舍五入。`.haha` 和 `.meme` 都是 4 个字符，所以 `n = len(label) + 5`。

链上必须用下面的整数算法。对 `n = 1..64` 它和 Python 生成器一致，包括恰好落在 `.5` 的情况。

```text
fsz = 42000 / (58 * n)          // 整数除法，向 0 截断
if fsz > 96: fsz = 96

num = fsz * 35
q = num / 100
r = num % 100
if r > 50 or (r == 50 and q % 2 == 1):
    q = q + 1
y = 250 + q
```

`n = 24` 时 `fsz = 30`，`y` 的小数部分正好是 `.5`。半偶数得到 **260**。如果实现成「`.5` 一律进位」，会得到 261，和已批准的生成器不一致。测试必须卡住这个点。

| fullName | n | fsz | y |
| --- | --- | --- | --- |
| `a.haha` | 6 | 96 | 284 |
| `abc.haha` | 8 | 90 | 282 |
| `myagent.meme` | 12 | 60 | 271 |
| `abcdefghijklmnopqrs.haha` | 24 | 30 | 260 |
| `superlongagentname2026.haha` | 27 | 26 | 259 |

`superlongagentname2026` 是 22 个字符，不是 23 个。

## 拼接

`y` 和字号都在同一个 `<text>` 标签中间，所以不能只切成前后两段。四段常量按这个顺序拼接，中间插入十进制数字和全名，不要补零、不要空格：

```text
prefix + decimal(y) + mid + decimal(fsz) + nameOpen + label + "." + tldString + suffix
```

`tldString` 是 `haha` 或 `meme`。拼出来的 UTF-8 字节必须等于 `svg(label, tldString)`。

label 只含 `a-z0-9`，tld 是固定英文。名字里没有 `<`、`&`、引号或非 ASCII，**不需要 XML 转义**。不要为了「以防万一」做 HTML escape，否则样例对不上。

## tokenURI

由 `HahaMetadata.build(string label, uint8 tld)` 返回，`HahaRegistrar.tokenURI` 只负责读出 label/tld 再调用它。SVG 常量放在 `HahaMetadata`，不要放进 Registrar。

合集的 ERC-721 `name()` 是 `haha id`，`symbol()` 是 `HAHAID`。下面 JSON 里的 `name` 仍是这一枚名字的全名，例如 `a.haha`。两处不要写成同一个字符串。

ERC-8004 身份 NFT 不使用另一张图。它的 `tokenURI` 指向注册文件；该文件的 `image` 必须是这里同一张 SVG 的 `data:image/svg+xml;base64,...`。身份合约不要再放一套 SVG 常量。

返回值是：

```text
data:application/json;base64,<base64(utf8(json))>
```

JSON 对象的字段顺序固定为 `name`、`description`、`image`、`attributes`。`image` 是：

```text
data:image/svg+xml;base64,<base64(utf8(svg))>
```

Base64 用标准字母表和 `=` 填充，中间不要换行。OpenZeppelin 的 `Base64.encode` 符合这个要求。

JSON 文本（`fullName` 形如 `a.haha`，`tldString` 形如 `haha`，`labelLength` 是 label 的字节长度）：

```json
{
  "name": "a.haha",
  "description": "haha.meme agent identity for a.haha",
  "image": "data:image/svg+xml;base64,...",
  "attributes": [
    {"trait_type": "TLD", "value": "haha"},
    {"trait_type": "Length", "display_type": "number", "value": 1}
  ]
}
```

- `name` 和 description 里的名字都不做转义，因为字符集不允许需要转义的字节。
- `Length` 是 JSON 数字，不是字符串。它统计 label，不统计 TLD 和点。
- 不把 agent 是否激活、积分、价格写进 metadata。那些会变，而这张图只表达名字。
- description 用英文，方便 OpenSea 一类市场。中文说明放在网站上。

测试要求：对三张样例，解码 `image` 后的 SVG 字节与 `assets/svg/samples/` 里的文件一致；JSON 的四个字段符合上面的模板。

## 体积与 gas

前缀大约 5.3 KB。加上 Base64 和 JSON 拼接，`HahaMetadata` 应当落在 24 KB 运行时上限以内。读取 `tokenURI` 是 `view`，用户用 `eth_call` 不付 gas，但链上再调用它会很贵。其他合约禁止在铸造或转账交易里调用 `tokenURI`。索引器应当缓存结果。

如果 `HahaMetadata` 的运行时字节码超过 24576，停下来报告，不要删渐变、图标或文字来硬塞。先确认编译器没有把同一段字符串复制两份。
