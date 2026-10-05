"""PROTOTYP: beste Schwellen je Variante/Bildrate/Haltung aus gitter.jsonl.
Harte Bedingungen: 0 Falschbuchungen, 0 Doppelbuchungen, 0 verlorene Exemplare. Dann max. Auto-Quote, dann min. p95-Dauer."""
import json, sys
from collections import defaultdict
erg = [json.loads(l) for l in open(sys.argv[1] + "/gitter.jsonl", encoding="utf-8")]
gr = defaultdict(list)
for e in erg: gr[(e["variante"], e["fps"], e["haltung"])].append(e)
print("variante       fps haltung   | gültig | auto  p50   p95   max  | sicher abst kons zeitl leer u_leer | prüf bremse verl_stör")
for k in sorted(gr):
    ok = [e for e in gr[k] if e["falsch"] == 0 and e["doppel"] == 0 and e["verloren"] == 0]
    if not ok: print(k, "keine gültige Konfiguration"); continue
    b = max(ok, key=lambda e: (e["auto_quote"], -(e["dauer_p95"] or 9e9)))
    print(f"{k[0]:14s} {k[1]:3d} {k[2]:9s} | {len(ok):6d} | {b['auto_quote']:.3f} {b['dauer_p50']:5} {b['dauer_p95']:5} {round(b['dauer_max']):5} | "
          f"{b['sicher_ab']:.2f}  {b['abstand']:.2f}  {b['konsens']}  {b['zeitlimit_ms']:5} {b['leer_bis_weg']}  {b['u_leer']:4} | {b['pruef_normal']:3d} {b['bremse']:3d} {b['verloren_stoer']:3d}")
