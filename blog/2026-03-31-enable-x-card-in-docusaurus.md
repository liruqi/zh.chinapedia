To enable X (formerly Twitter) cards in Docusaurus, you primarily configure the metadata within your docusaurus.config.js (or .ts) file. Docusaurus uses these settings to populate the <head> tags that social media platforms crawl to generate preview cards. [1, 2, 3] 
## 1. Global Configuration
Open your docusaurus.config.js and add or update the themeConfig object. This sets the default card behavior for your entire site. [2, 4, 5] 

// docusaurus.config.jsmodule.exports = {
  // ... other config
  themeConfig: {
    metadata: [
      {name: 'twitter:card', content: 'summary_large_image'},
      {name: 'twitter:site', content: '@YourTwitterHandle'},
      {name: 'twitter:creator', content: '@YourTwitterHandle'},
    ],
    image: 'img/docusaurus-social-card.jpg', // Path to your default social card image
  },
};

## 2. Individual Page Metadata
If you want a specific blog post or documentation page to have its own unique X card image, you can override the global settings using Front Matter at the top of your Markdown file. [1, 6] 

---title: My Awesome Page
description: A brief summary of this page for the X card.image: /img/unique-page-card.png
---# Your Content Here

## 3. Key Metadata Tags
Ensure these specific tags are present (either globally or per page) for the best results:

* twitter:card: Set to summary (small image) or summary_large_image (full-width image).
* twitter:image: The URL to the image. Docusaurus typically handles this via the image field in your config or front matter.
* og:title & og:description: X often falls back to Open Graph (OG) tags if specific Twitter tags are missing. [7, 8] 

## 4. Testing Your Card
After deploying your site, you can verify how the card looks using the X Post Validator (note: X has moved some validation features directly into the post composer preview, but third-party tools like OpenGraph.xyz are also excellent for testing). [9, 10, 11] 
Would you like to know how to automate social card generation for every page instead of creating images manually?

[1] [https://docusaurus.io](https://docusaurus.io/docs/markdown-features/head-metadata#:~:text=Docusaurus%20automatically%20sets%20useful%20page%20metadata%20in,extra%20metadata%20%28or%20override%20existing%20ones%29%20with)
[2] [https://docusaurus.io](https://docusaurus.io/docs/configuration)
[3] [https://www.socialchamp.com](https://www.socialchamp.com/blog/twitter-card-validator/#:~:text=Understanding%20Twitter%20Cards%20and%20Their%20Types%20To,videos%2C%20and%20other%20information%20to%20a%20tweet.)
[4] [https://docusaurus.io](https://docusaurus.io/zh-CN/blog/releases/3.0)
[5] [https://www.freecodecamp.org](https://www.freecodecamp.org/news/set-up-docs-as-code-with-docusaurus-and-github-actions/)
[6] [https://stackoverflow.com](https://stackoverflow.com/questions/71380664/how-to-add-twitter-card-image-to-individual-documentation-page)
[7] [https://www.tweetarchivist.com](https://www.tweetarchivist.com/twitter-card-validator-guide#:~:text=The%20card%20type%20tag%20looks%20like%20this:,choose%20summary%20for%20a%20more%20compact%20presentation.)
[8] [https://docusaurus.io](https://docusaurus.io/docs/2.x/seo#:~:text=Prefer%20to%20use%20front%20matter%20for%20fields,two%20metadata%20tags%20when%20using%20the%20tag.)
[9] [https://docusaurus.io](https://docusaurus.io/docs/seo#:~:text=To%20prevent%20your%20whole%20Docusaurus%20site%20from,may%20also%20let%20you%20configure%20a%20X%2D)
[10] [https://box464.com](https://box464.com/posts/mastodon-preview-cards/)
[11] [https://www.tweetarchivist.com](https://www.tweetarchivist.com/twitter-card-validator-guide#:~:text=This%20process%20usually%20completes%20within%20a%20few,%28%20X%20%28formerly%20Twitter%20%29%20%27s%20feed.)
