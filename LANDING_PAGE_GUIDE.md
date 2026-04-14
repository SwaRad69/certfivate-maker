# Landing Page YouTube Embed Instructions

The landing page is now set up to display a YouTube tutorial video. Here's how to add your YouTube embed:

## Option 1: Environment Variable (Recommended)

Set the `YOUTUBE_EMBED` environment variable before running the app:

### On Windows (PowerShell):
```powershell
$env:YOUTUBE_EMBED = '<iframe width="100%" height="auto" src="https://www.youtube.com/embed/YOUR_VIDEO_ID" title="Certificate Generator Tutorial" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="aspect-ratio: 16/9; border-radius: 10px;"></iframe>'

python .\app.py
```

### On Mac/Linux (Bash):
```bash
export YOUTUBE_EMBED='<iframe width="100%" height="auto" src="https://www.youtube.com/embed/YOUR_VIDEO_ID" title="Certificate Generator Tutorial" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="aspect-ratio: 16/9; border-radius: 10px;"></iframe>'

python app.py
```

### In .env file:
Create or edit a `.env` file in the `web/` directory:
```
YOUTUBE_EMBED=<iframe width="100%" height="auto" src="https://www.youtube.com/embed/YOUR_VIDEO_ID" title="Certificate Generator Tutorial" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="aspect-ratio: 16/9; border-radius: 10px;"></iframe>
```

## How to Get the Embed Code

1. Go to your YouTube video
2. Click **Share** → **Embed**
3. Copy the entire `<iframe>` code
4. Replace `YOUR_VIDEO_ID` with your actual video ID or use the full iframe code

## Example:

If your video URL is: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`

Then your embed code would be:
```html
<iframe width="100%" height="auto" src="https://www.youtube.com/embed/dQw4w9WgXcQ" title="Certificate Generator Tutorial" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="aspect-ratio: 16/9; border-radius: 10px;"></iframe>
```

## Option 2: Direct Edit in Code

If you prefer, you can directly edit the `app.py` file:

```python
@app.route('/')
def index():
    """Landing page - shown to unauthenticated users."""
    if 'credentials' in session:
        return redirect(url_for('dashboard'))
    
    youtube_embed = '<iframe width="100%" height="auto" src="https://www.youtube.com/embed/YOUR_VIDEO_ID" ... ></iframe>'
    
    return render_template('landing.html', youtube_embed=youtube_embed)
```

## Landing Page Features

- ✨ Modern, professional design with gradient backgrounds
- 📱 Fully responsive for mobile, tablet, and desktop
- ✅ 6 feature cards highlighting app benefits
- 📝 4-step instructions on how to use
- 📹 Video tutorial section (your embed goes here)
- 📊 Statistics section showing app capabilities
- 🎯 Multiple call-to-action buttons

## Customization

You can customize the landing page by editing `web/templates/landing.html`:
- Change the title, subtitle, or description
- Modify colors (currently using purple gradient: `#667eea` to `#764ba2`)
- Add or remove feature cards
- Edit the step-by-step instructions

## Testing

1. Run the app: `python .\app.py`
2. Visit: `http://localhost:5000`
3. You should see the landing page instead of being redirected to login
4. The YouTube video should display if you've set the `YOUTUBE_EMBED` variable

Enjoy! 🎉
