# Windows Terminal And Startup Status Notes

## Windows Terminal

If the AP radio monitor flickers on Windows, prefer Windows Terminal over legacy
Command Prompt.

Launch Windows Terminal from the Start menu:

1. Press the Windows key.
2. Type `Windows Terminal`.
3. Open it.
4. Run the monitor command from that terminal.

Launch from the Run dialog:

```text
Win + R
wt
```

Launch from an existing Command Prompt or PowerShell session:

```powershell
wt
```

Open Windows Terminal directly in a project folder:

```powershell
wt -d C:\path\to\ClientTracker
```

Then run the standalone monitor:

```powershell
python ap_radio_monitor_standalone.py --config ap_radio_monitor_standalone.handoff.yaml
```

If `wt` is not found, install **Windows Terminal** from the Microsoft Store.

## Flicker Mitigation Ideas

- Use Windows Terminal or PowerShell 7 instead of legacy `cmd.exe`.
- Use one display column on narrow terminals:

```yaml
ap_balance:
  display_columns: 1
```

- Lower row count on constrained displays:

```yaml
ap_balance:
  limit: 40
```

- Consider adding an alternate-screen option:

```yaml
ap_balance:
  alternate_screen: true
```

This would map to Rich `Live(..., screen=True)` and may reduce repaint flicker
on Windows by using the alternate screen buffer.

## Startup Status Ideas

The monitor can feel frozen while it connects and gathers initial data. Add
explicit startup indicators before the live table appears.

Recommended startup sequence:

1. `Loading config`
2. `Connecting to WLC <host>`
3. `Disabling terminal paging`
4. `Collecting AP radio load-info`
5. `Loading radio admin/oper state` when `auto_exclude_admin_down_slots` is enabled
6. `Rendering monitor`

Implementation options:

- Use `rich.status.Status` for a single spinner line during startup.
- Use a small Rich table or panel with each startup step and status.
- Keep startup status outside the live table so startup failures show clear
  context instead of a blank screen.

Suggested first implementation:

- Add a helper around startup steps in `run_once` and `run_live`.
- Print transient status messages through Rich before entering `Live`.
- If a startup step fails, show the step name and exception.
- Keep live refresh behavior unchanged.
