# Logo Assets

This directory contains logo and branding assets for PlantCareAI.

## Brand Name Usage

**Primary Brand Name:** **PlantCareAI** (without .app extension)

This is the official brand name used in all visual assets, product UI, and marketing materials. The ".app" extension is only used in specific contexts:

**Use "PlantCareAI":**

- All logos and visual branding
- Website headers and navigation
- Page titles and browser tabs
- Product UI and interface text
- Social media posts and casual references
- Spoken/verbal references

**Use "PlantCareAI.app":**

- Domain/URL references (https://plantcareai.app)
- Email addresses (updates@updates.plantcareai.app and hello@updates.plantcareai.app)
- Technical documentation referencing the domain
- Open Graph metadata (social sharing tags)

**Why:** "PlantCareAI" is easier to remember, say, and recall. It follows successful app naming conventions (Instagram, not Instagram.app). The shorter form reduces cognitive load and improves brand recognition.

## Files

### Header Banner

- **header-banner.png** (1356x327px)
  - Main site header banner with "PlantCareAI" logo
  - Rounded corners (16px radius) matching site design
  - Transparent background
  - Use in: Website header, documentation

### Email Banner

- **email-banner.png** (600x180px)
  - Optimized for email templates and marketing emails
  - Shows "PlantCareAI" branding with emerald leaf logo
  - Includes tagline: "Your plants deserve to thrive. We'll show you how."
  - Dark navy gradient background matching header banner
  - Compressed for fast loading (~49KB)
  - **Public URL**: `https://plantcareai.app/static/images/logos/email-banner.png`
  - **Retina version**: `email-banner@2x.png` (1200x360px) for high-DPI displays
  - Use in: Transactional emails, newsletters, notifications, landing pages

### OG Preview

- **og-preview.png** (1200x630px)
  - Social media preview image
  - Features "PlantCareAI" brand banner on gradient background
  - Maximized with 30px padding on sides
  - Optimized for Facebook, Twitter, LinkedIn sharing
  - Referenced in `base.html` meta tags

## Using Email Banner in Templates

### Supabase Email Templates

When creating email templates in Supabase, use the public URL:

```html
<img
  src="https://plantcareai.app/static/images/logos/email-banner.png"
  alt="PlantCareAI - Your plants deserve to thrive. We'll show you how."
  width="600"
  height="180"
  style="display: block; max-width: 100%; height: auto;"
/>
```

### Resend API Templates

For Resend API (hello@updates.plantcareai.app):

```html
<table
  width="100%"
  cellpadding="0"
  cellspacing="0"
  style="max-width: 600px; margin: 0 auto;"
>
  <tr>
    <td style="padding: 20px 0;">
      <img
        src="https://plantcareai.app/static/images/logos/email-banner.png"
        alt="PlantCareAI - Your plants deserve to thrive"
        width="600"
        height="180"
        style="display: block; width: 100%; height: auto;"
      />
    </td>
  </tr>
</table>
```

### Retina Display Support

For high-DPI displays (optional enhancement):

```html
<img
  src="https://plantcareai.app/static/images/logos/email-banner.png"
  srcset="https://plantcareai.app/static/images/logos/email-banner@2x.png 2x"
  alt="PlantCareAI"
  width="600"
  height="180"
  style="display: block; max-width: 100%; height: auto;"
/>
```

### Email Best Practices

1. **Always include alt text** for accessibility
2. **Specify width/height** to prevent layout shifts
3. **Use absolute URLs** (https://...) not relative paths
4. **Add border-radius** in inline styles for consistency
5. **Test in multiple email clients** (Gmail, Outlook, Apple Mail)

## Permissions

All static assets are served publicly by Flask and accessible without authentication. The email banner can be used in external emails without special CORS configuration.

## Updating Logos

If you need to regenerate these images:

1. Update source image: `header-banner.png`
2. Run the image processing script (saved in git history)
3. Commit updated images
4. Deploy to production
5. Clear CDN cache if using Cloudflare

## Image Specifications

| File                | Dimensions | Size   | Format | Use Case                       |
| ------------------- | ---------- | ------ | ------ | ------------------------------ |
| header-banner.png   | 1356x327   | ~85KB  | PNG    | Website header                 |
| email-banner.png    | 600x180    | ~49KB  | PNG    | Email templates, landing pages |
| email-banner@2x.png | 1200x360   | ~163KB | PNG    | Retina display emails          |
| og-preview.png      | 1200x630   | ~85KB  | PNG    | Social sharing                 |

## Brand Colors

For reference when creating new assets:

- **Primary Emerald**: #10b981 (Emerald 500)
- **Emerald 600**: #059669
- **Lime Green**: #a3e635 (Lime 400)
- **Gold**: #fbbf24 (Amber 400)
- **Navy Background**: #2d3561 to #1a1f3a gradient
- **Dark Navy**: #1e293b to #0f172a gradient (icons/cards)

**Text Gradient**: Emerald (#10b981) → Lime (#a3e635) → Gold (#fbbf24)

## Notes

- Email banner includes tagline for brand messaging
- Dark navy background works well in light and dark email clients
- Leaf logo uses outline style with visible veins for detail
- All text uses web-safe fonts for email compatibility
- Retina version (2x) available for high-DPI displays
