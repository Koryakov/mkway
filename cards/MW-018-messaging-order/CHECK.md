# MW-018 open check: socket and ref

Base: master 99182a7, branch t17. Session: pr-MW018-msg-check. Date 2026-11-11.
Copied into this card from branch t17 on 2026-11-11; the probe script `probe/wake_probe.py` is not copied (it was never run).

## (a) Can `mkway send` post a wake-up to another session through CLAUDE_CODE_MESSAGING_SOCKET?

Answer: **no** (not established as possible; the documented use is a session's OWN socket only).

Evidence:
- Variable in this session: a named pipe path of the form `\\.\pipe\LOCAL\cc-msg-<32 hex>`; the same string with the
  `uds:` prefix is what `/status` shows as Peer address. Native Windows, so a pipe, not a Unix socket.
- Public doc (code.claude.com/docs/en/cross-session-messaging, section "The session's inbox socket"): the variable is the
  address of the session's OWN inbox. A script posts to its own session's socket; the documented first line is
  `{"type":"auth","token":"<CLAUDE_CODE_MESSAGING_TOKEN>"}`. On native Windows that line is mandatory and the connection is
  closed otherwise; a silent connection is closed after 30 seconds.
- The token is per session and exported only to that session's own hooks and Bash. A command in this session holds its own
  token, not the token of another session, so it cannot authenticate to another session's pipe.
- The shape of the message line after the auth line is not documented publicly. It would be a guess.
- The one permitted try (a probe to the pipe of retro-oper10, body «MW-018 probe: socket wake-up test») was NOT run: the
  session's permission classifier refused the command (reason: containment escape). The probe script is kept at
  `probe/wake_probe.py`, never executed. No message was sent to any session by this check.

What card B should build: the fallback. `mkway send` writes the inbox row and prints the one-line ping (inbox id, sender,
kind); the sender then sends that line with the native SendMessage tool. The hook gate `message-not-in-inbox` already
fits this: the ping body carries the inbox id. Do not build a socket poster. Reopen only if the docs publish the message
line format and a cross-session token.

## (b) Is the [ref] of ListAgents the start of the session id that the hooks see?

Answer: **no** (for this session the ref is not a prefix of the session id).

Values side by side:

| Source | Value |
| --- | --- |
| ListAgents own row | `pr-MW018-msg-check [fa5e7a]` |
| env CLAUDE_CODE_SESSION_ID | `fe9af8db-3574-4315-88fe-5c38f6df30d4` |
| hook input session_id (mkway state) | not available: this worktree has no mkway hook entries and `python mkway.py sessions` reports `the profile cannot be read: (profile): not found`; the hook id is assumed equal to the env id (not established) |

`fa5e7a` is not the start of `fe9af8db`. The ref is another identifier of the session (its derivation is not documented).

What card B should build: key inboxes by the session id (as in the design), never by the ref. Show the ref only as a
convenience to humans. A ping line must carry the NAME the sender uses in SendMessage, plus the inbox id; do not derive
a recipient id from the ref. If a name-to-id map is needed, take it from the hook's session id plus the name recorded at
SessionStart (not established whether the hook input carries the name).
