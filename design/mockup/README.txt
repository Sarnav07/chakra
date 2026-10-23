CHAKRA - final UI mockup (visual reference only)
=================================================
These six files are the approved mockup, exported from the design canvas.
They are the VISUAL SPEC for the P4 prompts. They are NOT app code:
- they use a design-canvas format (<x-dc>, {{holes}}, <sc-for>, <sc-if>,
  class Component extends DCLogic) that React does not understand;
- every number in them is a SAMPLE, never copy numbers into the app;
- the video src "/_blob/..." only works inside the canvas. In the real app
  the same video is served by Vite at /media/chakra-bg.mp4
  (frontend/public/media/chakra-bg.mp4) with the still frame
  /media/chakra-bg-poster.jpg for reduced-motion users.

Copy from them: colours, fonts, sizes, spacing, radii, shadows, blur,
layout structure and wording of headings. Map each mockup screen to the
real page:
  Home.dc.html    -> frontend/src/pages/Home.jsx (route /)
  Main.dc.html    -> RiskMap.jsx (/map)
  Plan.dc.html    -> PlanTomorrow.jsx (/plan)
  Twin.dc.html    -> TwinLab.jsx (/twin)
  Worker.dc.html  -> Worker.jsx (/worker, phone layout)
  Check.dc.html   -> CheckItem.jsx (/check, phone layout)
Pages without a mockup screen (Reports, Mess log, Dashboard, Scale lab,
QR sheet, Bin QR page) use the same kit: they get the look automatically
through the shared ui components.

Design summary (the values P4 puts into tokens.css):
  Fonts: Instrument Serif (headings, one italic accent word per title),
         Inter 400/500/600 (body, numbers). Google Fonts.
  Text: headings #252B31, body #3F4A4B, muted #5E6A6B.
  Accent: #1E6B47 (italic word, active nav underline, chart highlight,
          leaf logo). Primary buttons are charcoal #252B31 pills.
  Background: the forest video, fixed, object-fit cover, with a
          rgba(255,255,255,0.30) veil on top; fallback colour #F3F6F4.
  Cards: rgba(255,255,255,0.82), backdrop blur 16px, border
          1px solid rgba(255,255,255,0.7), radius 16px, shadow
          0 25px 80px -12px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.05).
  Pills: radius 999px; badges = white pill with a coloured dot.
  Status/risk colours: unchanged from SPEC 16.5.

Credits that must stay with the app:
  Leaf logo icon: Lucide (ISC License, (c) Lucide Icons and Contributors)
    via AnimateIcons (MIT License, (c) 2025 Avijit Dey).
  Background video: taken from a third-party template prompt. Confirm you
    have the right to use it before showing it publicly; otherwise replace
    frontend/public/media/chakra-bg.mp4 with your own clip (same name).
