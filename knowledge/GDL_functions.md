# GDL Built-in Functions

## Math Functions

```gdl
ABS(x)           ! Absolute value
INT(x)           ! Integer part
SQRT(x)          ! Square root
SIN(angle)       ! Sine (angle in degrees)
COS(angle)       ! Cosine
TAN(angle)       ! Tangent
ASIN(x)          ! Inverse sine
ACOS(x)          ! Inverse cosine
ATAN(x)          ! Inverse tangent
```

### Common Math Operations

```gdl
x = 1 + 2 * 3           ! Multiplication, addition
x = (A + B) / 2         ! Division in parentheses
diagonal = SQRT(A^2 + B^2)  ! Pythagorean
angle = ATAN(B / A)     ! Calculate angle
```

## String Functions

```gdl
STR(number, decimals)   ! Convert number to string
STR(3.14159, 2)        ! "3.14"

LEN(string)            ! Length of string
LEN("Hello")           ! 5

UPPER(string)          ! Convert to uppercase
LOWER(string)          ! Convert to lowercase
```

## Conditional Functions

```gdl
MIN(a, b)              ! Minimum of two values
MAX(a, b)              ! Maximum of two values

IF condition THEN value1 ELSE value2  ! Inline if
```

## REQUEST (Query System)

REQUEST "string_id" param RETURNED_VALUE

```gdl
REQUEST "LibGDL" "GetObjectArea" result
! Returns the area of the object in 'result'

REQUEST "GDL_ModelView" type
! Returns current view type (2D/3D/Section)
```

## Common Patterns

### Calculate Center Point
```gdl
centerX = A / 2
centerY = B / 2
```

### Clamp Value to Range
```gdl
! Ensure value stays between min and max
IF param < minVal THEN param = minVal
IF param > maxVal THEN param = maxVal
```

### Calculate Diagonal
```gdl
diagonal = SQRT(A^2 + B^2)
```

### Convert Degrees to Radians (if needed)
```gdl
! GDL trig functions use degrees, not radians
angle_deg = 45
result = SIN(angle_deg)  ! Use degrees directly
```

## Important Notes

- Trigonometric functions in GDL use **degrees**, not radians
- String concatenation: use simple concatenation
  ```gdl
  label = "Width: " + STR(A, 2) + " m"
  ```
- Division by zero will cause errors, always check:
  ```gdl
  IF B <> 0 THEN
      ratio = A / B
  ENDIF
  ```
