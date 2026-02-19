# Common GDL Errors LLMs Make

## Error 1: Missing ENDIF

**Wrong:**
```gdl
IF bHasBack THEN
    BLOCK A, 0.02, backH
    ADD 0, B - 0.02, 0
```

**Right:**
```gdl
IF bHasBack THEN
    BLOCK A, 0.02, backH
    ADD 0, B - 0.02, 0
ENDIF
```

**Fix:** Every multi-line IF needs ENDIF. Single-line IF is OK without ENDIF.

---

## Error 2: PRISM_ Missing Height Parameter

**Wrong:**
```gdl
PRISM_ 4, 0, 0, 1, 0, 1, 1, 0, 1
```

**Right:**
```gdl
PRISM_ 4, 0.1, 0, 0, 1, 0, 1, 1, 0, 1
!        ↑    ↑
!        n    h (height - always needed!)
```

**Fix:** PRISM_ syntax is: `PRISM_ n, h, x1, y1, ..., xn, yn`
The second parameter is height, never omit it.

---

## Error 3: ADD/DEL Mismatch

**Wrong:**
```gdl
ADD 0, 0, 0.5
    BLOCK 1, 1, 1
ADD 0.5, 0, 0
    BLOCK 0.5, 0.5, 0.5
DEL 2  ! ← Wrong: only 1 transformation to pop
```

**Right:**
```gdl
ADD 0, 0, 0.5
    BLOCK 1, 1, 1
DEL 1

ADD 0.5, 0, 0
    BLOCK 0.5, 0.5, 0.5
DEL 1
```

OR (grouped):
```gdl
ADD 0, 0, 0.5
ADD 0.5, 0, 0
    BLOCK 0.5, 0.5, 0.5
DEL 2  ! ← Correct: delete 2 transformations
```

**Fix:** Every ADD must have a matching DEL. Count transformation layers carefully.

---

## Error 4: Single-line IF with ENDIF

**Wrong:**
```gdl
IF A < 0.5 THEN A = 0.5
ENDIF  ! ← Error: don't use ENDIF for single-line
```

**Right:**
```gdl
IF A < 0.5 THEN A = 0.5  ! No ENDIF needed
```

**Fix:** Single-line IF THEN doesn't need ENDIF. Only multi-line blocks need it.

---

## Error 5: NEXT Without FOR

**Wrong:**
```gdl
i = 1
BLOCK 1, 1, 1
NEXT i  ! ← Error: no FOR loop started
```

**Right:**
```gdl
FOR i = 1 TO 5
    BLOCK 1, 1, 1
NEXT i
```

**Fix:** NEXT must always have a matching FOR loop.

---

## Error 6: Boolean Values Not 0 or 1

**Wrong:**
```gdl
VALUES "bHasBack" TRUE, FALSE  ! ← GDL doesn't have TRUE/FALSE
VALUES "bHasBack" YES, NO      ! ← GDL doesn't have YES/NO
```

**Right:**
```gdl
VALUES "bHasBack" 0, 1
```

**Fix:** GDL Boolean is strictly 0 (FALSE) or 1 (TRUE).

---

## Error 7: Missing END in 3D Script

**Wrong:**
```gdl
! 3D Script
GOSUB "DrawLegs"
GOSUB "DrawSeat"
! Missing END
```

**Right:**
```gdl
! 3D Script
GOSUB "DrawLegs"
GOSUB "DrawSeat"
END
```

**Fix:** 3D Script must always end with `END`.

---

## Error 8: Using 2D/View Variables in Parameter Script

**Wrong:**
```gdl
! Parameter Script (VALUES)
IF GLOB_MODELVIEW_TYPE = 3 THEN
    VALUES "A" RANGE [0.3, 2.0]
ENDIF
```

**Right:**
```gdl
! Parameter Script should NOT use GLOB_MODELVIEW_TYPE
VALUES "A" RANGE [0.3, 2.0]
```

**Fix:** Parameter Script runs outside view context. Use only parameter validation, not view checks.

---

## Error 9: Forgetting Parameter Validation

**Wrong:**
```gdl
! 1D Script
! (Nothing - no validation)
```

**Right:**
```gdl
! 1D Script - always validate
IF A < 0.3 THEN A = 0.3
IF B < 0.3 THEN B = 0.3
IF ZZYZX < 0.5 THEN ZZYZX = 0.5
```

**Fix:** Always validate parameters in 1D Script to prevent geometry errors.

---

## Error 10: Undefined Subroutine Name

**Wrong:**
```gdl
GOSUB DrawLegs  ! ← Missing quotes
```

**Right:**
```gdl
GOSUB "DrawLegs"  ! ← Quotes required

"DrawLegs":
    ! Code
RETURN
```

**Fix:** Subroutine names must always be in quotes.
