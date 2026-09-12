# -*- coding: utf-8 -*-
"""Build the two updated decks from BioCore_for_Schools.pptx.

  BioCore_for_Schools_v2.pptx   - the school deck, with the review's fixes

  BioCore_x_QuickCampus.pptx    - the meeting deck, in the order the meeting runs:
      01-09  what BioCore is, as a standalone product
      10     where QuickCampus comes in
      11-15  the partnership case
      16-28  the school-facing deck (what their team would show a principal)
      29     appendix: questions for QuickCampus
"""
import os
from pptx import Presentation

import ds
import fixes
import product
import partnership as pk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "BioCore_for_Schools.pptx")

# partnership.s01 is dropped: the walk-in chain is now product slide 02, and the
# "no second ERP" line is the close of product slide 10.
PARTNER = [pk.s02, pk.s03, pk.s04, pk.s05, pk.s06]


def build_school():
    prs = Presentation(SRC)
    fixes.apply_all(prs, first=0)
    ds.renumber(prs)
    prs.save(os.path.join(ROOT, "BioCore_for_Schools_v2.pptx"))
    return len(prs.slides._sldIdLst)


def build_quickcampus():
    prs = Presentation(SRC)
    fixes.apply_all(prs, first=0)
    fixes.reframe_school_opener(prs.slides[0])

    front = product.BUILDERS + PARTNER
    for build in front:                       # appended at the end...
        build(prs)
    ds.move_to_front(prs, len(front))         # ...then moved ahead of the school deck
    pk.appendix(prs)                          # discussion questions go last

    ds.renumber(prs, right_footer=pk.FOOT)
    prs.save(os.path.join(ROOT, "BioCore_x_QuickCampus.pptx"))
    return len(prs.slides._sldIdLst)


def build_product():
    """BioCore on its own: no partner, no company, no commercials.

    The product section and the school deck overlapped in five places, so this
    keeps whichever slide told each part better and drops the other:
      deploy      -> product 08 (four options)   over school 04
      day-in-life -> product 05 (one timeline)   over school 05 + 06
      breadth     -> product 04 (seven uses)     over school 07
      open/closed -> school 08 (two panels)      over product 06
      privacy     -> school 09 + 10              over product 07
    """
    prs = Presentation(SRC)
    fixes.apply_all(prs, first=0)

    for build in (product.p01, product.p02, product.p03, product.p04,
                  product.p05, product.p08, product.p09):
        build(prs)

    #    cover  what-is  problem  example  not-a-machine  breadth  a-day
    order = [0,    13,      1,       14,        15,         16,     17,
             #  open/closed  photograph  DPDP  deploy  engine  personas  pilot  closer
                  7,           8,         9,    18,     19,      10,     11,    12]
    ds.arrange(prs, order)
    ds.renumber(prs, right_footer="Schools & colleges")
    prs.save(os.path.join(ROOT, "BioCore_Product.pptx"))
    return len(prs.slides._sldIdLst)


if __name__ == "__main__":
    print("school deck      :", build_school(), "slides")
    print("product deck     :", build_product(), "slides")
    print("quickcampus deck :", build_quickcampus(), "slides")
