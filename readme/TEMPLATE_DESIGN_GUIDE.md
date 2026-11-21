# Template Design Guide

Design your certificate in Canva, PowerPoint, or Google Slides. The web dashboard accepts a PowerPoint file or a native Google Slides presentation.

## Process Overview

1. Design the certificate and leave room for the recipient name and other dynamic fields.
2. If you start in Canva, download the design as `.pptx` and open it in PowerPoint.
3. Type placeholders such as `{{Name}}` into editable text boxes directly on the certificate slide.
4. In the web dashboard, choose **Upload from computer (.ppt or .pptx)** or select a native **Google Slides** presentation. The app converts an uploaded PowerPoint file when generation starts.

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

Open the downloaded file in PowerPoint to add or verify the editable text boxes. If you want to use the Google Slides chooser or CLI, open the file in Google Slides and save it as a native Google Slides presentation.

---

## Add Placeholders in PowerPoint or Google Slides

### Key Points

- Use double braces, as in `{{FieldName}}`.
- Match the data column name without regard to case. `{{Name}}` and `{{name}}` both use the `Name` column, with `Participant Name` as the fallback when `Name` is absent.
- Place the token in a regular editable text box on the slide. As part of the background, a picture, WordArt, or the Slide Master, it may be unavailable for replacement after conversion.

### Adding Placeholders

#### Option 1: Replace Existing Text

If your Canva design has sample text like "[Name]" or "[Your Name Here]":

1. Click the text box in PowerPoint or Google Slides
2. Select the sample text in the box
3. Type: `{{Name}}`
4. Click outside to deselect

#### Option 2: Create New Text Box

To add a new dynamic field:

1. Click **Insert** → **Text box**
2. Draw the text box where you want it
3. Type the placeholder: `{{FieldName}}`
4. Click outside to finish

#### Option 3: Find and Replace in Google Slides

If you have multiple fields to update:

1. Click **Edit** → **Find and replace** (Ctrl+H / Cmd+H)
2. Find: `[Name]` → Replace with: `{{Name}}`
3. Repeat for each field

### Example Template Text

Your certificate slide can use this text:

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

Provide a matching recipient data column for each placeholder. Column matching ignores capitalization. The `{{Name}}` placeholder checks `Name` before `Participant Name`.

### Example Mapping

These are the placeholders for the example template.
```
{{Name}}
{{Email}}
{{Event}}
{{Date}}
{{CompletionStatus}}
```

This CSV supplies the matching columns.
```csv
Name,Email,Event,Date,CompletionStatus
John Doe,john@example.com,Leadership Course,April 13 2024,Passed with Distinction
```

Extra columns can be used for PDF filenames or grouping, even when the template has no corresponding placeholder.

---

## Common Placeholder Examples

Here are common fields used in certificates:

| Placeholder | CSV Column | Example Value |
|-------------|-----------|----------------|
| `{{Name}}` | `Name` or `Participant Name` | John Doe |
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

1. Choose your data and template on the dashboard. Set **Test (First N)** to `1` and click **Start Test**.
2. Click **Open output folder** to open the PDF in the Drive folder ending in `(TEST)`.
3. Check that the recipient's values fit the text boxes and that the fonts and layout look right after conversion.

### Debug Command

```bash
python main.py --csv participants.csv --template YOUR_TEMPLATE_ID --verbose --output ./test_output
```

---

## Troubleshooting Template Issues

### Problem: Placeholders Not Detected

**Issue:** Tool says "No placeholders found"

**Solutions:**
1. Verify placeholders use exact syntax: `{{FieldName}}`
2. Check spelling matches CSV columns
3. Type the placeholder into a regular editable text box directly on the slide, then save and upload the PowerPoint again.
4. If the app names placeholders that conversion did not preserve, check those text boxes first. If it reports finding text in the Slide Master or a layout, add the editable placeholder to the certificate slide.

### Problem: Text Replacement Didn't Work

**Issue:** PDF still shows `{{Name}}` instead of actual name

**Solutions:**
1. Check that each placeholder has a matching data column. `{{Name}}` reads `Name` first, then `Participant Name` when `Name` is absent.
2. Check that the selected recipient rows have values in the matching columns.
3. Review the generation result for a missing column or a placeholder that conversion left out.

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
- For the CLI, share the native Google Slides template with the configured service account.
- Keep original Canva file (allows re-export if needed)
- Test download/open to verify file integrity

---

## Template Sharing for Google Slides

In the web dashboard, the signed-in Google account needs permission to read and copy the presentation. When using the CLI, share the template with the service account and give it permission to create temporary copies in the template's Drive folder.

1. Open your Google Slides template
2. Click **Share** (top right)
3. Paste the service account email:
   ```
   your-service-account@your-project.iam.gserviceaccount.com
   ```
4. Set access to **Editor**
5. Click **Share**

Check access to the parent Drive folder separately if the CLI cannot create a copy.

---

## Next Steps

Follow the [web quick start](WEB_QUICK_START.md) to generate from a PowerPoint or Google Slides template. See the [CLI reference](README.md) for command examples.

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
