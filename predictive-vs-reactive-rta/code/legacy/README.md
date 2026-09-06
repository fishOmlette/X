# Legacy coordination audit

These files preserve the first coordination prototype and the audit that exposed
its state-handling defect. They do not generate results used in the paper.

`legacy_coordination_simulator.py` permanently excluded a robot from later pair
checks after its first yield. The accompanying audit reproduces that behavior
and contrasts it with a minimal re-entry patch. The current experiment instead
uses `../coordination_simulator.py`, whose explicit state machine commits one
crossing order and releases each waiting robot only after its blockers clear.

The generated audit records live under `results/legacy/`.

Run the historical audit from the repository root with:

```powershell
python code\legacy\audit_coordination_state.py
```
