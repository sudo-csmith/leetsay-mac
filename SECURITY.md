# Security

leetsay is an open-source, volunteer-maintained project, provided "as is" without
warranty of any kind (see [LICENSE](LICENSE)). Security reports are welcome and
are looked at on a best-effort basis; no response time, fix or support is
promised.

## Supported versions

Only the latest version in this repository is maintained. Please update before
reporting a problem.

## Reporting a problem

If you find a security problem, please report it privately with GitHub's
**Report a vulnerability** button on this repository's **Security** tab,
rather than in a public issue. Include what you found, how to reproduce it,
and the leetsay version (shown in the title of the Settings window).

Please give a reasonable amount of time for a fix before describing the
problem publicly. There is no bug bounty.

## How leetsay is designed to protect you

- **Network blocked by design.** While it runs, leetsay blocks its own network
  access. The block is lifted only after you agree to a download (or for an
  update check you switched on, off by default), only towards `github.com`
  and GitHub's servers (and only to the addresses
  those names lead to), and is restored when the download or update check is
  done (the update check is off by default and asks first). It never
  listens for incoming connections. The block is checked each time it starts
  offline (not when a download agreed to in Settings is about to run).
- **Checked model files.** Every file of the speech model is compared with a
  SHA-256 fingerprint built into leetsay before it is used. A file that does
  not match is not used: leetsay offers only to download it again, or to
  quit. A download goes into a separate folder and replaces the old files only
  once every new file has been checked.
- **Checked connections.** Downloads use HTTPS and are verified against the
  certificates this Mac trusts (macOS's own certificate check, as in Safari),
  and every file is still checked against its built-in fingerprint. leetsay
  never switches the certificate check off. A company's security
  program that inspects connections (Netskope, Zscaler) works if macOS trusts
  its certificate; the model's files are still checked against their built-in
  fingerprints, so such a program could block or watch the download but not
  change the files unnoticed.
- **No code from beside the program.** Run as a script, leetsay does not load
  stray Python files from its own folder.
- **Careful with your typing.** The hotkey is watched with a listen-only
  keyboard tap: it cannot change or block your typing. leetsay never types
  while macOS's secure input is on (password fields), and with Text box
  detection on (the default) it types only when the cursor is in a text box.
  Only if you switch them on, it can paste with ⌘V (borrowing the clipboard
  for about a second) and press Return, ⌘ Return or Tab after typing (hold to
  confirm). With **Stay in the app I started in** (on by default) it can ask
  macOS to bring the app you started in back to the front.
- **Checked settings lines.** A settings line pasted into Import settings can
  only set known options to valid values; switching a safety check off, or
  switching on anything that pastes, keeps text, presses a key for you or goes
  online, needs your agreement.

## Limits

- The network block works inside Python. The speech engine, the window library
  and the audio library are compiled code that the block cannot inspect. They
  are not used to go online, but only a firewall can enforce that at the level
  of macOS.
- The Accessibility permission lets an app watch the keyboard and type into
  other apps. leetsay uses it only for its hotkey and for typing your words,
  but macOS cannot limit an app to that: give it only to apps you trust, and
  download leetsay only from this repository's Releases page.
- Releases are signed with an Apple Developer ID and notarised by Apple, so
  macOS checks who made a download and that it hasn't been changed before it
  opens. You can also check the SHA-256 fingerprint on the release page (see
  the README). The 0.0.x test versions were not signed.
- The speech model's files are checked against their SHA-256 fingerprints
  when they arrive and whenever their size or date changes; unchanged files
  are not hashed again at every start. Someone who can already change files
  in your user account could get round this, as they could change leetsay
  itself.
- While the network is open for a download, a proxy server set on your Mac is
  allowed too, so the download can go through it.
- No software is free of bugs. Use leetsay at your own risk.
