# Wp2Tumblr.py
I realized that there are no migrators from Wordpress to Tumblr, so I wrote this one.
Be careful while you use it, if you run it more than once, you will end up with duplicate posts.
Read the damn code, before you run it :-D

### What it does ?
* Parses your Wordpress Extended RSS and makes a list of posts, comments
* Publishes all your posts @ Tumblr
* Posts all your image-attachments as private posts in Tumblr
* Posts all your comments @ Disqus
	
### What do you need ?
* Wordpress Extended RSS file of your wordpress blog
* A Tumblr Blog - Email and Password
* Disqus API KEY for comments

### What does it depend on ?
* Python ~2.6
* Diqus-Python API from Rajat Upadhyaya. Thanks man.
	
### Known bugs ?
* Even though I'm updating links to images in your posts, I'm not updating references to other posts on your blog. You might have to do this manually.
* I saw a few HTTP 400s when creating threads with ' in their title though I'm encoding values in HTTP Post params to UTF-8. I din't care as those posts were very old. Even though, I would love to fix this problem. So, let me know the exact error if you face it.

### What next ?
* Read the code before running and it worked properly fine on my machine
* No, I might not be able to help you migrate your blog, but sure I can guide you how to do it
* Feel free to fork and make it work
