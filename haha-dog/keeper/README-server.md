Haha Dog snapshot keeper (python port of haha-dog/keeper/keeper.sh). Service: haha-dog-keeper.service
Key + RPC list come from systemd LoadCredential (no copy on disk): /etc/haha/admin-signer.env, /etc/haha/indexer.env.
Stop: systemctl stop haha-dog-keeper   Logs: journalctl -u haha-dog-keeper
