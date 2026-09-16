---
name: Silent Moon (MIND-FLOW)
description: A calm, restorative, and minimalist design system inspired by modern mindfulness and meditation applications.
tokens:
  colors:
    primary:
      light: "#8E97FD"
      dark: "#8E97FD"
    primary-variant:
      light: "#EBEAEC"
      dark: "#2A2A3A"
    secondary:
      light: "#FFC97E"
      dark: "#FFC97E"
    background:
      light: "#F2F3F7"
      dark: "#1A1A24"
    surface:
      light: "#FFFFFF"
      dark: "#232336"
    surface-variant:
      light: "#FAFAFA"
      dark: "#2C2C40"
    on-primary:
      light: "#FFFFFF"
      dark: "#FFFFFF"
    on-secondary:
      light: "#3F414E"
      dark: "#1A1A24"
    on-background:
      light: "#3F414E"
      dark: "#F6F1FB"
    on-surface:
      light: "#3F414E"
      dark: "#F6F1FB"
    on-surface-variant:
      light: "#A1A4B2"
      dark: "#A1A4B2"
    border:
      light: "rgba(63, 65, 78, 0.05)"
      dark: "rgba(246, 241, 251, 0.05)"
    accent-1:
      light: "#FF84A2"
      dark: "#FF84A2"
    accent-2:
      light: "#7583CA"
      dark: "#7583CA"
    accent-3:
      light: "#F0B68E"
      dark: "#F0B68E"
    accent-4:
      light: "#82C1B8"
      dark: "#82C1B8"

  typography:
    family:
      sans: "'Nunito', 'Inter', system-ui, -apple-system, sans-serif"
    weights:
      light: 300
      regular: 400
      medium: 500
      semibold: 600
      bold: 700
    sizes:
      h1: "2rem"
      h2: "1.5rem"
      h3: "1.25rem"
      body-lg: "1.125rem"
      body: "1rem"
      body-sm: "0.875rem"
      caption: "0.75rem"

  spacing:
    xs: "0.25rem"
    sm: "0.5rem"
    md: "1rem"
    lg: "1.5rem"
    xl: "2rem"
    xxl: "3rem"

  radii:
    sm: "0.5rem"
    md: "0.75rem"
    lg: "1.25rem"
    xl: "1.5rem"
    full: "9999px"

  shadows:
    sm: "0 2px 4px rgba(0,0,0,0.02)"
    md: "0 4px 12px rgba(0,0,0,0.05)"
    lg: "0 8px 24px rgba(0,0,0,0.08)"
    dark-md: "0 4px 12px rgba(0,0,0,0.2)"
    dark-lg: "0 8px 24px rgba(0,0,0,0.4)"

  effects:
    glass-bg:
      light: "rgba(255, 255, 255, 0.7)"
      dark: "rgba(35, 35, 54, 0.7)"
    glass-blur: "blur(12px)"
---

# Silent Moon Design System

## Overview

The Silent Moon design language is built to be a digital sanctuary. It focuses on reducing cognitive load, providing soft boundaries, and bringing a sense of calm to the user's workflow. It draws heavily from mindfulness aesthetics: generous whitespace, soft rounded corners, non-intrusive typography, and a color palette inspired by twilight and the morning sky.

## Colors

- **Primary (`#8E97FD`)**: A calming, muted periwinkle blue that suggests serenity and focus.
- **Secondary (`#FFC97E`)**: A warm, sunrise yellow-orange used for gentle accents and highlights.
- **Backgrounds**: The light mode relies on a very soft grey-blue (`#F2F3F7`) to reduce eye strain compared to pure white. The dark mode uses a deep, rich twilight purple-grey (`#1A1A24`).
- **Accents**: The system provides 4 accent colors (pink, deep blue, peach, and mint) that can be used for different meditation or focus categories (e.g., Sleep, Focus, Anxious, Kids).

## Typography

- **Nunito** is the primary typeface. Its rounded terminals make it feel friendly, approachable, and soft—perfect for a restorative experience.
- Headings should be bold (700) but not overly large.
- Body text should be readable (regular 400 or medium 500) with a muted text color (`on-surface-variant` for secondary text) to avoid harsh contrast.

## Layout and Spacing

- **Breathe**: Elements should have plenty of room to breathe. Minimum padding for most containers is `lg` (1.5rem).
- **Curved Edges**: Sharp corners are aggressive. Nearly everything should have a border-radius. Cards use `lg` (1.25rem) or `xl` (1.5rem), and buttons use `full` (pill shape).

## Components

### Cards
Cards are the primary structural element (used for courses, daily thoughts, and analytics).
- They should have the `surface` background color.
- They should use the `lg` or `xl` border-radius.
- In light mode, they have a soft `shadows.md`. In dark mode, they rely more on a subtle border or `shadows.dark-md`.
- Active or featured cards might have their background set to `primary` or one of the accent colors.

### Buttons
- Primary buttons should be pill-shaped (`radii.full`).
- They should stand out but not scream for attention. Use `primary` background with `on-primary` text.

### Navigation (Bottom Bar / Side Bar)
- The navigation should feel grounded. Active states can be denoted by the `primary` color or a soft pill background behind the active icon.

## Do's and Don'ts

- **Do** use whitespace to group items rather than hard dividers.
- **Do** use the accent colors to differentiate categories without overwhelming the screen.
- **Don't** use pure black (`#000000`) or pure white (`#FFFFFF`) for large background areas.
- **Don't** use sharp corners (`0px` border-radius) on interactive elements or cards.
- **Don't** clutter the screen with too much text. Keep copy minimal and let the layout speak.
