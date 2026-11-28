const M = require("../site/js/haha-ai-model.js");
for (const s of process.argv.slice(2)) console.log(s, "0x" + M.hex(M.keccak256(M.utf8(s))).slice(0, 8));
