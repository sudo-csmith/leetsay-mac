# Privacy

This page describes how leetsay for Mac handles information. leetsay is
open-source software that runs on your own Mac. Its author does not run any
server or service for it and does not receive, collect or store any
information about you or your use of it.

This page describes how the software is designed to behave. It is not a
contract and gives no guarantee; leetsay is provided "as is", without warranty
of any kind (see [LICENSE](LICENSE) and the Disclaimer in the
[README](README.md)). You can check every statement here yourself by reading
the source code.

## What the developer collects

Nothing. leetsay has no accounts, no analytics, no telemetry, no crash
reporting, no advertising and no servers of its own. The developer has no way
to see who uses it or what they do with it.

## Your voice and your words

- Speech is turned into text on your Mac by a speech model running on your
  Mac. leetsay is designed not to send audio or text anywhere and not to save
  audio to disk. Audio is held in memory while you dictate and released
  afterwards.
- The microphone is opened only while you dictate, while you use the
  microphone test in Settings, and for a moment when you click **Allow the
  microphone** in the setup (if macOS's own request can't be made), so that
  macOS asks you.
- The text is typed into the app you are using, as key presses. By default
  leetsay does not use the clipboard, and it never writes the text to disk or
  to its log. While you dictate, the words heard so far are shown on the
  pop-up and kept in memory until the dictation ends.
- **Paste using the clipboard** (Settings › Privacy, off by default): the
  text is put on the clipboard for about a second, pasted, and then what you
  had copied is put back. It is marked "concealed" and "transient" (the
  markers clipboard managers use to leave things out of their history), but
  other apps that watch the clipboard could see it during that second.
- **Type as you speak** (Settings › Typing, off by default): the words are
  typed into your app while you are still speaking, instead of when you let
  go. They go only into the app you started in, and (with Text box detection
  on, the default) only into a text box; never into a password field.
- **Missed text safety** (Settings › Privacy, off by default): your last
  dictation is kept in leetsay's memory for 5 minutes, so a quick tap of the
  hotkey (or a key you choose) can type it again. It is never written to disk
  or left on the clipboard. It is dropped after 5 minutes or when leetsay
  quits, and replaced by your next dictation. Turning the option off drops it
  at once.
- **Pressing a key for you** (Settings › General, off by default): after
  typing your words, leetsay can press Return, ⌘ Return or Tab for you. In
  many apps that sends a message or a form straight away; you are responsible
  for where you use it.
- Once the text is typed into another app (a chat, an email, a web page, a
  document), that app has it, and its own privacy terms apply. leetsay cannot
  see or control what another app does with your text. If that app is online,
  the text may leave your Mac through it.
- To notice its hotkey, leetsay watches the keyboard while it runs, with
  macOS's Accessibility permission, as any app with a global hotkey must. It
  only checks whether the hotkey is held on its own; it does not record or
  store key presses.
- **Text box detection** (on by default): while you dictate, to say "No text
  box selected" when the cursor isn't in one, and to type nothing then,
  leetsay asks macOS's accessibility service (the one screen readers use) what
  kind of control has the keyboard focus: a text box, a password field, a
  button or a page. It does not read the text in it, the page or the window's
  title. The answer is used on the spot and is not stored, logged or sent
  anywhere. Turn it off and macOS is asked only whether the focus is a
  password field (never typed into). Either way, leetsay never types while
  macOS's "secure input" is on (as it is in password fields).
- **The app you dictate into:** when you start a dictation, leetsay asks macOS
  which app is in front (its name and where it is installed), to show that
  app's icon on the pop-up (on by default), to tint the glow with the icon's
  colour (on by default), and to show its name (off by default). While you
  dictate it also checks which app is in front, so your words go into the app
  you started in (**Stay in the app I started in**, on by default, asks macOS
  to bring that app back if another one took over). This is used on the spot;
  it is not stored, logged or sent anywhere.
- **Full-screen apps:** while the small pill shows between dictations, leetsay
  asks macOS every few seconds where the windows of the app in front are
  (their place and size only, never their titles, contents or the app's
  name), so the pill can step aside while a game or a full-screen video
  covers its screen. Nothing is stored, logged or sent anywhere. With
  **Show it over full-screen apps too** on, or the pill turned off, it isn't
  asked.
- **Word replacements** (the ones you add in Settings) are kept in your
  settings file on this Mac. They are not included when you export your
  settings, and are never sent anywhere.
- **Microphone test** (Settings › Audio): it listens for about 6 seconds and
  shows the words it heard. They are not typed anywhere and not kept.
- **Try it** (in the setup window): the words you dictate into its box are
  cleared when the window closes.

## What leetsay reads from macOS

To work, leetsay asks macOS a few questions. It changes nothing in macOS
except the items marked below, and only when you choose them.

- Whether leetsay has the Accessibility and Microphone permissions (to show
  their status, and to guide you through the setup).
- The list of microphones (to let you choose one, and to show a red light
  when there is none). This does not open or listen to any microphone.
- The list of speakers and headphones (Settings › Audio › Sounds › Output),
  and the `.wav` files you choose there for your own start and finish sounds.
- macOS's **Reduce motion** setting (with it on, the pop-up doesn't animate).
- macOS's own certificate check, only while a download you agreed to is
  running, to check that it really is github.com.
- **Start at login** adds leetsay to your Login Items. It is switched on when
  you finish setup (as "Start with Windows" is ticked on Windows), never
  before; untick it in Settings › General and it is removed. **Setup and permissions** open pages of System Settings; the
  permissions themselves are switched on or off by you, in System Settings.
- **Also only when you use them:** **Paste using the clipboard** borrows the
  clipboard for about a second and then puts back what was there; **Stay in
  the app I started in** (on by default) asks macOS to bring the app you
  started in back to the front if another one took over while you spoke; the
  startup update check, if you switched it on, can show a macOS notification
  when a newer version is out.

## The network

- While it runs, leetsay blocks its own network access, except as described
  below. It checks this block each time it starts offline (not when a
  download you agreed to in Settings is about to run); the check does not
  leave your Mac. The result is shown in Settings › Privacy and in its log.
- It connects to the internet only after you agree in a window that says
  **"This application will go online"**, and only to `github.com` (and
  `release-assets.githubusercontent.com` and `objects.githubusercontent.com`,
  GitHub's servers that deliver the files), a third-party website that we do
  not run or control. It downloads from this project's model page there. That
  happens:
  - the first time you start it, to download the speech model (about 660 MB)
    and a small speech detector (about 2 MB);
  - if you choose another speech model in Settings, or download one again.
- If your Mac uses a proxy server (set in System Settings or in the usual
  proxy environment variables), the connection goes through it, as any
  download would.
- When it connects, standard technical information that any download involves
  (such as your IP address and the files requested) reaches GitHub and the
  networks in between. That is handled under GitHub's own privacy policy, not
  this one. leetsay sends no account details or identifiers of its own.
- When the download is finished (or has failed three times in a row), the
  network block is restored.
- Your agreement to a download is not remembered: each download asks again.
  (The update check at startup is the one exception: you agree once, when you
  switch it on, and can switch it off at any time.)
- **Check for updates** (Settings › Privacy, off by default): **Check now**
  asks first, with the same "This application will go online" window; the
  check at startup is asked about once, when you switch it on. It connects to
  `api.github.com` only, to read the version number of the latest published
  release of leetsay for Mac. Nothing is downloaded or installed: if there is
  a newer version, leetsay tells you, and you can open its page in your web
  browser yourself. The network block is restored straight after the check.
- **Report a problem** and **Suggest an idea** open a page in your web
  browser, after a notice. leetsay itself does not go online for this.

## What is stored on your Mac

In `~/Library/Application Support/leetsay`:

- `settings.json`: your settings. Besides your choices, these include the
  name of the microphone you picked (a device's name can contain a person's
  name, such as "Jane's headset"), where you placed the pop-up, your word
  replacements, the paths of any sound files you chose (a path can contain
  your user name), the name of the sound output you picked, your colour and
  look choices, the last newer version the update check told you about, which
  notices you have already seen, and a note of when the
  speech model's files were last checked against their fingerprints. A
  settings file that can't be read is kept as `settings.json.damaged`;
  `settings.json.saving` exists only for a moment while settings are saved.
- `leetsay.lock`: which copy of leetsay is running (process number and
  version), so a second copy doesn't start.
- `tick.png`: a small picture used for ticked boxes in Settings.
- `models/`: the speech model and the speech detector. While a download runs,
  it goes to a folder ending in `.download`, which replaces the old one only
  once every file has been checked.

In `~/Library/Logs/leetsay`:

- `leetsay.log`: a short technical log of the current session (start-up,
  network check, model loading, how long readings took). It is designed not
  to contain anything you said or the names of apps you use, and is started
  afresh each time leetsay starts. Your home folder is written as `~`, so it
  doesn't show your user name.

These files stay on your Mac; keeping your Mac secure is up to you.

## Third parties

- **GitHub** (where leetsay and its speech models are published) is a
  third-party website that we do not run or control. Its own terms and
  privacy policy apply when you use it.
- **Apple's macOS** asks for and keeps the permissions you give leetsay;
  Apple's own terms apply to macOS.
- The speech model and libraries leetsay uses are made by others; see
  [CREDITS.md](CREDITS.md).

## Children

leetsay collects nothing from anyone, children included: there are no
accounts, and nothing is sent to us.

## Reporting a problem

The "Report a problem" and "Suggest an idea" buttons open GitHub's issue forms
in your browser. Anything you write there, and any log you choose to attach,
is **public** on GitHub, under GitHub's own terms and privacy policy. Read a
log before you attach it. Security problems should be reported privately
instead; see [SECURITY.md](SECURITY.md).

## Removing everything

See "Uninstalling" in the [README](README.md).

## Changes

This page may change when leetsay changes. The current version is always the
one in this repository.
