# GDL 2D Commands

## Basic Shapes

### Rectangle
```gdl
RECT2 x1, y1, x2, y2
! Draws axis-aligned rectangle from (x1,y1) to (x2,y2)

RECT2 0, 0, A, B
```

### Polygon
```gdl
POLY2 nVertices, x1, y1, x2, y2, ..., xn, yn
! Closed polygon with n vertices

POLY2 4, 0, 0, 1, 0, 1, 1, 0, 1  ! 4 vertices
```

### Circle/Arc
```gdl
CIRCLE2 x, y, radius
! Full circle at (x, y)

CIRCLE2 0.5, 0.5, 0.3

ARC2 x, y, radius, angle1, angle2
! Arc from angle1 to angle2 (in degrees)

ARC2 0.5, 0.5, 0.3, 0, 90  ! Quarter circle
```

### Line
```gdl
LINE2 x1, y1, x2, y2

LINE2 0, 0, 1, 1
```

## Hotspots (Resize Handles)

HOTSPOT2 places interactive resize points in 2D view:

```gdl
HOTSPOT2 0, 0       ! Corner
HOTSPOT2 A, 0       ! Right corner
HOTSPOT2 A, B       ! Opposite corner
HOTSPOT2 0, B       ! Left corner

HOTSPOT2 A/2, 0     ! Midpoint for height dragging
HOTSPOT2 A, B/2     ! Midpoint for width dragging
```

Users can drag these to resize the object.

## Fill and Pen Properties

### Pen (Line Color)
```gdl
PEN penNumber  ! 1-255
PEN 1          ! First pen
```

### Fill Pattern
```gdl
FILL fillNumber  ! 0 = empty, 1 = solid, etc.
FILL 1           ! Solid fill

FILL 0           ! No fill (hollow)
```

### Fill Color
```gdl
FILLCOLOR r, g, b   ! RGB 0.0 - 1.0
FILLCOLOR 1, 0, 0   ! Red
```

### Combined Example
```gdl
PEN 1              ! Black outline
FILLCOLOR 0.8, 0.8, 0.8  ! Gray fill
FILL 1             ! Solid
RECT2 0, 0, A, B
```

## Transformations in 2D

```gdl
ADD2 dx, dy      ! Translate (2D only)
DEL2 n           ! Remove n ADD2 transformations

ROTZ2 angle      ! Rotate around Z (in 2D)

SETFILL pattern
SETPEN pennum
SETC2 r, g, b    ! RGB color
```

## Typical 2D Script Structure

```gdl
! ============
! 2D SCRIPT
! ============

PEN 1
FILL 1
FILLCOLOR 0.7, 0.7, 0.7

! Draw main outline
RECT2 0, 0, A, B

! Draw internal details if needed
PEN 2
CIRCLE2 A/2, B/2, 0.1

! Always add hotspots for dragging
PEN 1
HOTSPOT2 0, 0
HOTSPOT2 A, 0
HOTSPOT2 A, B
HOTSPOT2 0, B
HOTSPOT2 A/2, B/2
```

## Important Notes

- 2D commands use 2D suffix: RECT2, POLY2, CIRCLE2, etc.
- Always include HOTSPOT2 for user interaction
- Pen numbers: 1-255 (check ArchiCAD's pen table)
- Angles in degrees, 0° = right, 90° = up
