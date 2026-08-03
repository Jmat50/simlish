"""
Small character seq2seq EN→Simlish with leave-one-song-out style holdout.
Trains lightly if torch is available; always writes a distilled char-map fallback.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from v2.config import LYRICS_DIR, MODELS_DIR, PHRASE_LM_DIR, ensure_dirs


def load_pairs() -> list[tuple[str, str, str]]:
    rows = []
    for fp in LYRICS_DIR.glob("*.json"):
        doc = json.loads(fp.read_text(encoding="utf-8"))
        sid = doc["song_id"]
        for p in doc.get("pairs") or []:
            rows.append((sid, p["original"].lower(), p["simlish"].lower()))
    return rows


def distill_char_map(pairs: list[tuple[str, str, str]]) -> dict:
    """Alignment-free global char translation priors + bigrams from zip trunc."""
    uni: dict[str, Counter] = {}
    for _, en, sim in pairs:
        for a, b in zip(en, sim):
            uni.setdefault(a, Counter())[b] += 1
    return {
        k: v.most_common(1)[0][0]
        for k, v in uni.items()
        if k.isalpha() or k in " '"
    }


def augment(en: str, sim: str, lex: dict) -> list[tuple[str, str]]:
    out = [(en, sim)]
    # case / punct noise
    out.append((en.upper(), sim.upper()))
    if len(en) > 8:
        cut = max(4, len(en) // 3)
        out.append((en[cut:], sim[cut:] if len(sim) > cut else sim))
    return out


def train_torch(pairs: list[tuple[str, str, str]]) -> bool:
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Dataset
    except Exception as exc:  # noqa: BLE001
        print(f"torch unavailable: {exc}")
        return False

    chars = sorted(set("".join(e + s for _, e, s in pairs)) | set("\n"))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    pad = 0
    if "\0" not in stoi:
        # use index 0 as pad by shifting — keep simple: pad token = space reuse
        pass

    class PairDS(Dataset):
        def __init__(self, rows):
            self.rows = rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, idx):
            _, en, sim = self.rows[idx]
            x = torch.tensor([stoi.get(c, 0) for c in en[:80]], dtype=torch.long)
            y = torch.tensor([stoi.get(c, 0) for c in sim[:80]], dtype=torch.long)
            return x, y

    def collate(batch):
        xs, ys = zip(*batch)
        xmax = max(t.size(0) for t in xs)
        ymax = max(t.size(0) for t in ys)
        xb = torch.zeros(len(xs), xmax, dtype=torch.long)
        yb = torch.zeros(len(ys), ymax, dtype=torch.long)
        for i, (x, y) in enumerate(batch):
            xb[i, : x.size(0)] = x
            yb[i, : y.size(0)] = y
        return xb, yb

    class SeqModel(nn.Module):
        def __init__(self, n_char, dim=128):
            super().__init__()
            self.emb = nn.Embedding(n_char, dim)
            self.encoder = nn.GRU(dim, dim, batch_first=True)
            self.decoder = nn.GRU(dim, dim, batch_first=True)
            self.out = nn.Linear(dim, n_char)

        def forward(self, x, y):
            xe = self.emb(x)
            _, h = self.encoder(xe)
            ye = self.emb(y)
            yo, _ = self.decoder(ye, h)
            return self.out(yo)

    # leave one song out holdout: last song id alphabetically
    songs = sorted({s for s, _, _ in pairs})
    hold = songs[-1]
    train_rows = [r for r in pairs if r[0] != hold]
    # augment
    lex_path = MODELS_DIR / "soundalike_rules.json"
    lex = {}
    if lex_path.exists():
        raw = json.loads(lex_path.read_text(encoding="utf-8")).get("lexicon", {})
        lex = {k: v[0]["simlish"] for k, v in raw.items() if v}

    aug = []
    for sid, en, sim in train_rows:
        for a, b in augment(en, sim, lex):
            aug.append((sid, a, b))
    random.shuffle(aug)

    ds = PairDS(aug)
    dl = DataLoader(ds, batch_size=16, shuffle=True, collate_fn=collate)
    model = SeqModel(len(chars))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss(ignore_index=0)
    model.train()
    for epoch in range(6):
        total = 0.0
        n = 0
        for xb, yb in dl:
            # teacher forcing: input y shifted
            inp = yb[:, :-1]
            tgt = yb[:, 1:]
            if inp.numel() == 0 or tgt.numel() == 0:
                continue
            # encode x, decode with inp — simplify: use x length truncate
            logits = model(xb[:, : inp.size(1)], inp)
            m = min(logits.size(1), tgt.size(1))
            loss = loss_fn(logits[:, :m].reshape(-1, len(chars)), tgt[:, :m].reshape(-1))
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item())
            n += 1
        print(f"epoch {epoch+1} loss={total/max(1,n):.4f} holdout_song={hold}")

    PHRASE_LM_DIR.mkdir(parents=True, exist_ok=True)
    ckpt = {
        "stoi": stoi,
        "itos": {str(k): v for k, v in itos.items()},
        "state_dict": model.state_dict(),
        "holdout_song": hold,
        "dim": 128,
    }
    torch.save(ckpt, PHRASE_LM_DIR / "seq2seq.pt")
    print(f"saved {PHRASE_LM_DIR / 'seq2seq.pt'}")
    return True


def main() -> None:
    ensure_dirs()
    pairs = load_pairs()
    char_map = distill_char_map(pairs)
    (PHRASE_LM_DIR / "char_map.json").write_text(
        json.dumps(char_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"distilled char_map entries={len(char_map)}")
    train_torch(pairs)


if __name__ == "__main__":
    main()
