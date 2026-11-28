import json,os,urllib.request
from eth_utils import keccak
U=[l.split("=",1)[1].split(",")[0] for l in open("/etc/haha/indexer.env") if l.startswith("BSC_RPC_URLS=")][0].strip()
D="0x26f88A5db4925e9aFa35B1096FdD6DBa09f056c6"
def rpc(m,p):
    r=json.load(urllib.request.urlopen(urllib.request.Request(U,json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),{"content-type":"application/json","user-agent":"x"}),timeout=10))
    return r["result"]
def s(x): return "0x"+keccak(text=x)[:4].hex()
def c(sig,*a):
    return rpc("eth_call",[{"to":D,"data":s(sig)+"".join(f"{v:064x}" for v in a)},"latest"])
blk=int(rpc("eth_blockNumber",[]),16)
ts=int(c("totalSupply()"),16); h=int(c("queueHead()"),16); l=int(c("queueLength()"),16)
print("block",blk,"supply",ts,"queueHead",h,"queueLen",l)
for t in range(1,ts+1):
    r=c("dogOf(uint256)",t)[2:]; w=[int(r[i*64:(i+1)*64],16) for i in range(5)]
    commit,target,rr,st=w[0],w[1],w[2],w[3]
    print(f"dog#{t} status={st} commit={commit} target={target} rerolls={rr} blocks_since_target={blk-target} {'(seed set)' if w[4] else ''}")
bal=int(rpc("eth_getBalance",["0x083A467259f12602E9053bBAe2b3Fd5B62976Ef7","latest"]),16)
print("balance_bnb",bal/1e18)
