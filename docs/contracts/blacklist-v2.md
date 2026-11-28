# 黑名单 v2

状态：已通过。日期：2026-11-20。共 **208** 个归一化词。本文件与 `blacklist-v2.txt`、`blacklist-v2.hashes.txt` 一起作为链上名单的源。

这些词会原样进入仓库，是为了让合约拒绝它们。网站不要把这份清单展示给用户。

## 链上规则

- 合约收到的 `label` 必须已经是 `^[a-z0-9]+$`。合约不再做大小写转换，也不删除符号。含大写、空格、连字符、下划线、点、汉字或 emoji 的输入直接 revert。
- 哈希：`keccak256(abi.encodePacked("HAHA_V2", label))`。`encodePacked` 把两个字符串的原始字节拼在一起，中间没有长度头、没有 `0x00`。不要用 `abi.encode`。
- 精确匹配。`binanceofficial`、`b1nance` 不算命中。这两类只由网站拦截。
- 部署时写入 `HahaNamePolicy` 的 mapping，构造函数跑完就冻结。没有 owner，没有增删函数。管理员也不能注册这些名字。
- 存储方式见 `SPEC.md`：构造函数写 mapping，不使用 Merkle。调用 `register` 的代理不需要带 proof。

## 校验值

字母序 208 个哈希（每个 32 字节）首尾相接，再做一次 `keccak256`，结果必须是：

`0xb9bda22217d260c2032c02472ab75de873d668a59e15358431284b2e99ff41e1`

单条测试向量：

- `trump` → `0x2fb81193c412e0605114fa0de2c7586df93ccb4eca5678d1781f0dd83394cb41`
- `btc` 不在名单中，`isBlacklisted("btc")` 必须为 false。

`blacklist-v2.hashes.txt` 每行是 `词<空格>0x哈希`，按字母序，共 208 行。部署脚本必须从本词表现场计算哈希，并与该文件逐行相等，否则中止部署。

## 分类

### B1. 党政军 / 机构 / 敏感历史 / 分裂相关（90）

`ccp`, `cpc`, `communist`, `communistparty`, `zhongguogongchandang`, `pla`, `gov`, `government`, `state`, `army`, `military`, `police`, `officer`, `general`, `marshal`, `chairman`, `premier`, `minister`, `governor`, `mayor`, `secretary`, `dang`, `gongchandang`, `zhonggong`, `dangzhongyang`, `zhongyang`, `zhengfu`, `guowuyuan`, `renda`, `zhengxie`, `jiwei`, `jianwei`, `jiefangjun`, `renminjiefangjun`, `wujing`, `gongan`, `guoan`, `jingcha`, `junguan`, `shangjiang`, `zhongjiang`, `shaojiang`, `jiangjun`, `yuanshuai`, `zhuxi`, `zongshuji`, `zongli`, `buzhang`, `shengzhang`, `shizhang`, `shuji`, `weiyuan`, `lianghui`, `rendadaibiao`, `zhengxieweiyuan`, `junwei`, `zhengzhiju`, `changwei`, `buwei`, `bangongting`, `jiguan`, `zhanqu`, `junqu`, `zhongxuanbu`, `zhongzubu`, `zhengfawei`, `fagaiwei`, `waijiaobu`, `guofangbu`, `gonganbu`, `guoanbu`, `tiananmen`, `liusi`, `8964`, `wenge`, `wenhuadageming`, `falungong`, `lunzi`, `xiejiao`, `quannengshen`, `zangdu`, `jiangdu`, `taidu`, `gangdu`, `dongtu`, `dongyiyun`, `xizangduli`, `xinjiangduli`, `taiwanduli`, `xianggangduli`

### B2. 国家领导人（现任与历届）（42）

`xijinping`, `xjp`, `liqiang`, `likeqiang`, `zhaoleji`, `wanghuning`, `caiqi`, `dingxuexiang`, `lixi`, `hanzheng`, `wangyi`, `maozedong`, `chairmanmao`, `zhouenlai`, `dengxiaoping`, `jiangzemin`, `hujintao`, `zhude`, `liushaoqi`, `huaguofeng`, `wenjiabao`, `zhurongji`, `lipeng`, `qiaoshi`, `liruhuan`, `putin`, `biden`, `trump`, `harris`, `kimjongun`, `zelensky`, `modi`, `macron`, `sunak`, `starmer`, `kishida`, `ishiba`, `yoon`, `leejaemyung`, `scholz`, `meloni`, `erdogan`

### B3. 仇恨言论（44）

`nigger`, `nigga`, `chink`, `chinky`, `gook`, `spic`, `kike`, `wetback`, `beaner`, `coon`, `darkie`, `paki`, `raghead`, `towelhead`, `nazi`, `hitler`, `gestapo`, `swastika`, `fascist`, `heil`, `kkk`, `kukluxklan`, `whitepower`, `whitepride`, `neonazi`, `antisemite`, `islamophobe`, `faggot`, `fag`, `dyke`, `tranny`, `genocide`, `ethniccleansing`, `gaschamber`, `heigui`, `zhina`, `zhinazhu`, `xiaoriben`, `ribenguizi`, `bangzi`, `asan`, `baipizhu`, `nige`, `dongyabingfu`

### B4. 儿童色情（最高优先级）（9）

`childporn`, `childlover`, `lolicon`, `shotacon`, `ageplay`, `preteen`, `loli`, `lolis`, `underage`

### B5. 恐怖主义 / 极端组织（16）

`isis`, `isil`, `daesh`, `alqaeda`, `taliban`, `bokoharam`, `hamas`, `hezbollah`, `alshabaab`, `terror`, `terrorist`, `terrorism`, `jihad`, `extremism`, `extremist`, `radicalization`

### B6. 其他违法（7）

`scam`, `scammer`, `fraud`, `phishing`, `phish`, `ponzi`, `moneylaundering`

## 明确不拉黑

- 姓氏拼音单独出现时不拉黑：`mao`、`deng`、`jiang`、`hu`、`xi`、`li`、`wang`。`xi`、`li`、`hu` 长度为 2，公众仍不能注册，原因是保留短名，不是黑名单。
- 公开可注册：`btc`、`bitcoin`、`eth`、`sol`、`usdt`、`usdc`、`bnb`、`lido`、`crypto`、`satoshi`、`wallet`、`exchange`。
- `trump` 留在黑名单里。
