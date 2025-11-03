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
- Email addresses (noreply@plantcareai.app)
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
- **email-banner.png** (600x144px)
  - Optimized for email templates
  - Shows "PlantCareAI" branding
  - Rounded corners, transparent background
  - Compressed for fast loading (~32KB)
  - **Public URL**: `https://plantcareai.app/static/images/logos/email-banner.png`
  - Use in: Transactional emails, newsletters, notifications

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
  alt="PlantCareAI - Your plants deserve to thrive"
  width="600"
  height="149"
  style="display: block; max-width: 100%; height: auto;"
/>
```

### Resend API Templates

For Resend API (noreply@plantcareai.app):

```html
<table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
  <tr>
    <td style="padding: 20px 0;">
      <img
        src="https://plantcareai.app/static/images/logos/email-banner.png"
        alt="PlantCareAI"
        width="600"
        height="149"
        style="display: block; width: 100%; height: auto; border-radius: 16px;"
      />
    </td>
  </tr>
</table>
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

| File | Dimensions | Size | Format | Use Case |
|------|-----------|------|--------|----------|
| header-banner.png | 1356x327 | ~85KB | PNG | Website header |
| email-banner.png | 600x144 | ~32KB | PNG | Email templates |
| og-preview.png | 1200x630 | ~68KB | PNG | Social sharing |

## Brand Colors

For reference when creating new assets:

- **Primary Teal**: #0f766e
- **Teal 600**: #0d9488
- **Teal 700**: #115e59
- **Sage Green**: #8BA888
- **Background**: Gradient from #0d9488 to #115e59

## Notes

- Email banner is optimized for dark mode email clients
- Transparent background works on any email background color
- Rounded corners match site design system (16px)
- All text uses web-safe fonts for email compatibility
