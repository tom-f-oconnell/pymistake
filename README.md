
Put these scripts in a directory on `PYTHONPATH` to get better stack traces.

If this code can determine that the session is not interactive
(in the being-run-by-a-person, e.g. from a terminal, sense; not the
`sys.flags.interactive` sense), then the `excepthook` will not be modified.

