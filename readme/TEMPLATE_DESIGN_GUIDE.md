# Template Design Guide

This document provides guidance on designing your certificate template in Canva and converting it to Google Slides.

## Process Overview

1. **Design in Canva** — Create your certificate design with layouts, colors, images
2. **Export from Canva** — Export as PPTX (preferred)
3. **Upload to Google Drive** — Upload the PPTX file
4. **Open in Google Slides** — Google auto-converts it
5. **Add Placeholders in Google Slides** — Replace text with `{{Placeholder}}`
6. **Share with Service Account** — Grant the service account editor access

---

## Design Tips (Canva)

### What Works Well

- **Simple layouts:** One text block per dynamic field works best
- **Readable fonts:** Sans-serif fonts (Arial, Roboto) display well
- **Spacing:** Leave room for text that might be longer than your example
- **High DPI export:** PPTX format preserves quality better than PNG

### What to Avoid

- **Too much animation:** Google Slides may not preserve Canva animations
- **Complex overlays:** Multiple text layers can be hard to target
- **Small text:** Ensure placeholder text is readable size
- **Gradients with text:** Can sometimes render differently

### Example Canva Design Structure

```
┌─────────────────────────────────────┐
│                                       │
│        Certificate of Completion      │
│                                       │
│         [Add Logo/Image Here]        │
│                                       │
│  This certifies that [Name in here]  │
│                                       │
│   has successfully completed the     │
│                                       │
│  [Event Name/Course Title Here]      │
│                                       │
│  on [Date Here]                      │
│                                       │
│  ─────────────────────────────────  │
│  Signature            Date           │
│                                       │
│  Email: [Email Here]                 │
│                                       │
└─────────────────────────────────────┘
```

---

## Export from Canva

### Step 1: Download as PPTX

1. Click **Share** or **Download** button
2. Select **Download** 
3. Choose **PowerPoint (.pptx)** format
4. Click **Download**

This preserves formatting much better than exporting as image.

### Step 2: Upload to Google Drive

1. Go to [Google Drive](https://drive.google.com/)
2. Click **New** → **File upload**
3. Select your downloaded PPTX file
4. Wait for upload to complete

### Step 3: Open in Google Slides

1. Right-click the uploaded file
2. Click **Open with** → **Google Slides**
3. Google automatically converts the PPTX
4. Wait for conversion (usually instant)

---

## Add Placeholders in Google Slides

### Key Points

- **Placeholder syntax:** `{{FieldName}}`
- **Case-sensitive:** `{{Name}}` ≠ `{{name}}`
- **Must match CSV columns:** Column name in CSV = Placeholder name
- **Edit in Google Slides, not Canva**

### Adding Placeholders

#### Option 1: Replace Existing Text

If your Canva design has sample text like "[Name]" or "[Your Name Here]":

1. Click on that text box in Google Slides
2. Triple-click to select all text in the box
3. Type: `{{Name}}`
4. Click outside to deselect

#### Option 2: Create New Text Box

To add a new dynamic field:

1. Click **Insert** → **Text box**
2. Draw the text box where you want it
3. Type the placeholder: `{{FieldName}}`
4. Click outside to finish

#### Option 3: Find & Replace (Bulk)

If you have multiple fields to update:

1. Click **Edit** → **Find and replace** (Ctrl+H / Cmd+H)
2. Find: `[Name]` → Replace with: `{{Name}}`
3. Repeat for each field

### Example Template Text

In your Google Slides, each dynamic section might look like:

```
Certificate of Completion

This certifies that

    {{Name}}

has successfully completed the

    {{Event}}

on {{Date}}

Contact: {{Email}}

Date: {{Date}}
```

---

## Placeholder Mapping

Your CSV column names MUST match placeholder names exactly.

### Example Mapping

**Google Slides placeholders:**
```
{{Name}}
{{Email}}
{{Event}}
{{Date}}
{{CompletionStatus}}
```

**Required CSV columns:**
```csv
Name,Email,Event,Date,CompletionStatus
John Doe,john@example.com,Leadership Course,April 13 2024,Passed with Distinction
```

**Rules:**
- All placeholders must have matching CSV columns
- Extra CSV columns are OK (they're just ignored)
- Column names are case-sensitive

---

## Common Placeholder Examples

Here are common fields used in certificates:

| Placeholder | CSV Column | Example Value |
|-------------|-----------|----------------|
| `{{Name}}` | Name | John Doe |
| `{{Email}}` | Email | john@example.com |
| `{{Date}}` | Date | April 13, 2024 |
| `{{Event}}` | Event | Spring Conference |
| `{{Department}}` | Department | Engineering |
| `{{Grade}}` | Grade | A+ |
| `{{Hours}}` | Hours | 40 |
| `{{Location}}` | Location | San Francisco, CA |
| `{{CourseName}}` | CourseName | Advanced Python |
| `{{InstructorName}}` | InstructorName | Dr. Jane Smith |

---

## Testing Your Template

Before generating all certificates:

### Test Steps

1. **Verify placeholders are present:**
   - Run tool with `--verbose` flag
   - Log will show detected placeholders
   - Verify all {{Placeholder}} are detected

2. **Test with sample CSV:**
   - Use `sample_participants.csv` included in project
   - Or create a 1-row test CSV
   - Generate one certificate
   - Check the PDF output looks correct

3. **Check text replacement:**
   - Values should appear where placeholders were
   - No `{{Placeholder}}` text should remain
   - Formatting should look professional

### Debug Command

```bash
python main.py --csv sample_participants.csv --template YOUR_TEMPLATE_ID --verbose --output ./test_output
```

---

## Troubleshooting Template Issues

### Problem: Placeholders Not Detected

**Issue:** Tool says "No placeholders found"

**Solutions:**
1. Verify placeholders use exact syntax: `{{FieldName}}`
2. Check spelling matches CSV columns
3. Ensure text is in a text box or shape (not just floating)
4. Try clicking into text box and re-typing the placeholder

### Problem: Text Replacement Didn't Work

**Issue:** PDF still shows `{{Name}}` instead of actual name

**Solutions:**
1. Verify CSV column name matches placeholder name exactly (case-sensitive)
2. Check for extra spaces: `{{ Name}}` won't match `{{Name}}`
3. Ensure CSV has data in that row/column (no empty cells)

### Problem: Formatting Changed After Export

**Issue:** Text looks different in PDF vs Google Slides

**Solutions:**
1. Google Slides → PDF is lossy conversion; minor difference is normal
2. Test with sample to see expected result
3. Adjust template colors/fonts if needed
4. Use simpler fonts (Arial, Roboto) for better consistency

### Problem: Template Conversion Failed

**Issue:** PPTX → Google Slides conversion created strange layout

**Solutions:**
1. Download PPTX from Canva again (different quality)
2. Try exporting as PNG and manually recreating in Google Slides
3. Simplify the Canva design (fewer elements, less complex layouts)

---

## Best Practices

### Design

- Use simple, clean layouts
- Leave space around placeholders for longer text
- Test with longest expected values (name, email, etc.)
- Use high-contrast colors for readability

### Placeholders

- Use consistent naming (all lowercase path, CamelCase, or snake_case)
- Keep placeholder names short and memorable
- Document placeholder names in README or comment in CSV
- Test with sample CSV before full batch

### Export

- Use PPTX format (preserves better than PNG)
- Share template with service account before generating
- Keep original Canva file (allows re-export if needed)
- Test download/open to verify file integrity

---

## Template Sharing

**Important:** before running the generator, share the template with the service account email.

1. Open your Google Slides template
2. Click **Share** (top right)
3. Paste the service account email:
   ```
   your-service-account@your-project.iam.gserviceaccount.com
   ```
4. Set access to **Editor**
5. Click **Share**

The service account needs **Editor** access to:
- Read the template
- Create copies
- Update text
- Export as PDF

---

## Next Steps

1. **Design your template** in Canva
2. **Export as PPTX** and upload to Google Drive
3. **Open in Google Slides** and add `{{Placeholder}}` text
4. **Share with service account** (see Setup Guide)
5. **Test** with sample CSV
6. **Generate certificates** with full dataset

See [README.md](README.md) for command examples.

---

## Reference: PPTX Compatibility

**Well-supported Canva elements:**
- Text blocks / text boxes
- Colors and fills
- Images and shapes
- Fonts (most standard fonts)
- Simple layouts

**Sometimes problematic:**
- Animations
- Complex designs with many overlays
- Some decorative fonts
- Gradient backgrounds with text

If PPTX import has issues, simplify your Canva design or recreate in Google Slides.
