# How to read the "How to read" lines

Five charts in this tool cannot be decoded from their axes alone: the two topic planes on
**Find**, the topic overlay and the balance bars in **Compare**'s topic overlap, and the
reciprocity scatter in **Compare**'s relationship section. Each of them prints one short line
between its own controls and the chart itself. The lines live in `docs/how_to_read.yaml` and are
read through `lib/how_to_read.py` (`text(chart, mode)`, `methods(key)`).

## Why the line is visible, not a tooltip

Every one of these charts changes what it draws when the reader changes a control. The topic
selector has five settings, and on the balance bars each setting changes the **quantity in the
bars**, not merely which topics are listed; the reciprocity scatter switches between fields and
the pair's top subfields. A reader who has to hover, or open a Methods page, to find out what
the marks currently mean will read the wrong chart instead — most often the previous one. So the
line is always on screen, and it changes with the control: the text names the state the chart is
actually in.

## The reading pattern: encode, reference, order, example

Every chart line follows the same four beats, in the same order, so the reader learns the shape
once and then skims it:

1. **Encode** — what a mark is and what each channel carries (position, length, area, colour).
2. **Reference** — the line or tick the reader measures against, when the chart draws one: the
   red dashed line at the European average of 1.0, the tick at world rank twenty, the zero rules
   on the frontier axes, the dotted equal-weight diagonal. Where the chart has no reference mark,
   the beat is simply absent rather than invented.
3. **Order** — how the set on screen was chosen and sorted, because the selector's cut is part of
   the meaning: the ten-paper floor under the impact cut, "world top twenty" under topics led,
   the world's fastest-moving decile under emergence, the thirty subfields with the most joint
   publications.
4. **Example** — one worked reading a reader can check against the picture in front of them
   ("a bubble far to the right and above the line is…"). The example is what turns a legend into
   an interpretation.

House rules, enforced by `tests/test_how_to_read.py`: one or two sentences, at most 340
characters, no abbreviations, no internal vocabulary, and every (chart, mode) key present.

## Where the frontier definition comes from

Expansion and acceleration are not this tool's own inventions, and the wording here is taken
from **the score author's method note and the 3-year-bin score workbook** that ships the scores.
Both were re-read for this pass, because the earlier wording ("how fast the volume grew over the
latest period") described expansion as a growth rate, which it is not.

The scores are computed on three-year bins of world publication volume, 2004-06 through 2019-21,
plus a two-year latest bin, 2022-23.

- **Expansion is a position.** How far the topic's world volume in the latest bin sits above or
  below the global baseline, standardised across topics. Zero means the topic has expanded no
  more than science as a whole over the long run.
- **Acceleration is momentum.** The topic's growth against that same baseline between 2019-21 and
  2022-23, standardised. Zero means it is moving with science as a whole.
- **The frontier score** weighs the two: 0.7 expansion plus 0.3 acceleration.

The reading the two together support, and the example the copy carries: a topic at expansion 0.01
with acceleration 0.5 has an average long-run position but gained momentum in 2022-23. The same
two definitions are held in the `methods` block of the yaml, so the Methods page's "Frontier
scores" section and the caption under the topic planes cannot drift apart from the chart lines.
