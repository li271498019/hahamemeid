"""Shared model definition.

Decoder (the part that ships on-chain):
    z (8)  --Linear-->  H (ReLU)  --Linear-->  OUT = 128*2 + 26
  * first 256 outputs: a 2-D point per half-cell (16 rows x 8 cols)
  * cell class = argmax_k ( 2*y.P_k - |P_k|^2 ), P = 11 learned 2-D prototypes
    (= nearest prototype, integer friendly)
  * last 26 outputs: color-choice logits  fur(7) cloth(8) acc(6) glow(5)
Encoder (training only): one-hot cells + picks -> mu, logvar (VAE).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

N_CELLS = 128
N_CLASSES = 11
GROUP_SIZES = [7, 8, 6, 5]           # fur, cloth, acc, glow
N_PICK = sum(GROUP_SIZES)
LATENT = 8


def fake_q(w, levels=127):
    """int8 symmetric per-tensor fake quantization with straight-through gradient."""
    s = w.detach().abs().max().clamp(min=1e-8) / levels
    return w + (torch.round(w / s) * s - w).detach()


class Decoder(nn.Module):
    """hidden: int or list of ints (ReLU layers). Output layer is linear."""

    def __init__(self, hidden=32, cell_masks=None):
        """cell_masks: (128, 11) bool - which classes ever occur in each half-cell
        (from the training sheets). Cells with a single possible class are
        constant (drawn from a fixed table, no network output); for the others
        the argmax only considers that cell's allowed classes."""
        super().__init__()
        hs = [hidden] if isinstance(hidden, int) else list(hidden)
        if cell_masks is None:
            cell_masks = torch.ones(N_CELLS, N_CLASSES, dtype=torch.bool)
        cell_masks = torch.as_tensor(cell_masks, dtype=torch.bool)
        self.register_buffer("cell_masks", cell_masks)
        var = (cell_masks.sum(1) > 1).nonzero().flatten()
        self.register_buffer("var_cells", var)
        self.n_var = len(var)
        dims = [LATENT] + hs
        self.hidden_layers = nn.ModuleList([nn.Linear(dims[i], dims[i + 1]) for i in range(len(hs))])
        self.out = nn.Linear(hs[-1], self.n_var * 2 + N_PICK)
        self.proto = nn.Parameter(torch.randn(N_CLASSES, 2) * 2.0)
        self.qat = False
        self.register_buffer("s_h", torch.ones(len(hs)))

    def _hidden(self, z, quant):
        h = z
        for i, l in enumerate(self.hidden_layers):
            h = F.relu(F.linear(h, fake_q(l.weight) if quant else l.weight, l.bias))
            if quant:
                hq = torch.clamp(torch.round(h / self.s_h[i]), 0, 127) * self.s_h[i]
                h = h + (hq - h).detach()
        return h

    def calibrate(self, n=20000):
        with torch.no_grad():
            h = irwin_hall_z(n)
            for i, l in enumerate(self.hidden_layers):
                h = F.relu(F.linear(h, fake_q(l.weight), l.bias))
                self.s_h[i] = float(torch.quantile(h.flatten()[:1000000], 0.9999)) / 127 + 1e-8
                hq = torch.clamp(torch.round(h / self.s_h[i]), 0, 127) * self.s_h[i]
                h = hq

    def forward(self, z):
        h = self._hidden(z, self.qat)
        if self.qat:
            o = F.linear(h, fake_q(self.out.weight), self.out.bias)
            P = fake_q(self.proto)
        else:
            o = self.out(h)
            P = self.proto
        y = o[:, :self.n_var * 2].view(-1, self.n_var, 2)
        var_logits = 2 * torch.einsum("bnd,kd->bnk", y, P) - (P * P).sum(1)
        B = z.shape[0]
        # constant cells: a big logit on their only class
        cell_logits = (self.cell_masks.float() * 50.0 - 25.0).unsqueeze(0).repeat(B, 1, 1)
        m = self.cell_masks[self.var_cells]
        cell_logits[:, self.var_cells] = var_logits.masked_fill(~m, -1e4)
        return cell_logits, o[:, self.n_var * 2:]

    def n_params(self):
        return sum(p.numel() for n_, p in self.named_parameters())


class Encoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(N_CELLS * N_CLASSES + N_PICK, 512), nn.ReLU(),
                                 nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, LATENT * 2))

    def forward(self, x):
        o = self.net(x)
        return o[:, :LATENT], o[:, LATENT:]


def encode_input(cells, picks):
    """cells: (B,128) long ; picks: (B,4) long with -1 = unused."""
    x1 = F.one_hot(cells, N_CLASSES).float().view(cells.shape[0], -1)
    parts = []
    for g, n in enumerate(GROUP_SIZES):
        p = picks[:, g]
        oh = F.one_hot(p.clamp(min=0), n).float() * (p >= 0).float()[:, None]
        parts.append(oh)
    return torch.cat([x1] + parts, 1)


def pick_loss(pick_logits, picks):
    loss, off = 0.0, 0
    for g, n in enumerate(GROUP_SIZES):
        lg = pick_logits[:, off:off + n]; off += n
        t = picks[:, g]
        m = t >= 0
        if m.any():
            loss = loss + F.cross_entropy(lg[m], t[m])
    return loss


def irwin_hall_z(n, gen=None):
    """Same latent distribution the contract uses: per dim, sum of 4 random bytes."""
    b = torch.randint(0, 256, (n, LATENT, 4), generator=gen)
    s = b.sum(-1) - 510
    zq = torch.div(s * 7, 32, rounding_mode="floor")
    return zq.float() / 32.0
