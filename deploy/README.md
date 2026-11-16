# Deploy sul minipc (systemd, utente `sheol`)

Un timer utente esegue `update.sh` ogni giorno alle 06:30 dal clone in `~/tv-iptv-it`.
Serve un IP italiano: i flussi geobloccati sembrano morti da fuori.

Setup una tantum:

```bash
# 1. deploy key dedicata a questo repo (scrittura), solo per questo job
ssh-keygen -t ed25519 -N "" -C "minipc tv-iptv-it deploy" -f ~/.ssh/tv-iptv-it_deploy
gh repo deploy-key add ~/.ssh/tv-iptv-it_deploy.pub -R clemeg/tv-iptv-it --allow-write

# 2. alias SSH su porta 443 (stesso schema degli altri deploy del server)
cat >> ~/.ssh/config <<'EOF'
Host github-tv-iptv
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/tv-iptv-it_deploy
  IdentitiesOnly yes
EOF

# 3. clone e identità git locale al repo
git clone git@github-tv-iptv:clemeg/tv-iptv-it.git ~/tv-iptv-it
git -C ~/tv-iptv-it config user.name  "minipc"
git -C ~/tv-iptv-it config user.email "minipc@users.noreply.github.com"

# 4. unità systemd utente (linger già attivo)
mkdir -p ~/.config/systemd/user
cp ~/tv-iptv-it/deploy/tv-iptv-update.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tv-iptv-update.timer
```

Controllo: `systemctl --user list-timers tv-iptv-update.timer` e `journalctl --user -u tv-iptv-update`.
Esecuzione manuale: `systemctl --user start tv-iptv-update.service`.
