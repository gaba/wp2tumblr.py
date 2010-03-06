#!/usr/bin/env python
"""
    wp2tumblr.py
    Python script for migrating your Wordpress blog to Tumblr
    Karteek Edamadaka
"""

import os
import sys
import urllib
import urllib2
import datetime
import time
import logging
import pickle
import re
import json
import disqus


GENERATOR = 'KMigrator 0.3'
TUMBLRWRITE = 'http://www.tumblr.com/api/write'
TUMBLRREAD = 'http://karteek.tumblr.com/api/read/json'
# Update with your TumblrSite/api/read/json
TUMBLREMAIL = 'spammers@spammers.com'
# Update with your Tumblr login Email
TUMBLRPASS = 'TEHPASSWORD'
# Update with your Tumblr login password
DISCUSAPIKEY = "P8HrZSPmBZjtDkX18prxxL6RD73stJV9HraZeEZT3J8RGmIz2Z"
# Update with your Disqus API Key
# Get it at http://disqus.com/api/get_my_key/
# Dont forget to register your Tumblr site at Disqus
WXR = 'wordpress.yyyy-mm-dd.xml'
# Update with your file name of your Wordpress Extended RSS file
BASEURL = "http://karteek.tumblr.com/post/"
# Update with your TumblrSite/post
OBJECTFILE = "posts.obj"
# Above object remembers all the parsed posts and their comments
SUCCESSFILE = "success.obj"
# Above object remembers all the posts which are posted to Tumblr to avoid 
# reposting in case of failures

logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

def main():
    print("Welcome to Wordpress to Tumblr Migrator")
    print("""Steps I do
        1. Read and parse your Wordpress Archive
        2. Get your disqus forum list
        3. For each post
           - if any images are involved, I post them to Tumblr
           - then, modify your post and update the <img> srcs
           - I post the post the modified posts to your Tumblr
           - I migrate all the comments of that post to disqus
        4. The End
        
        Note: If program stops responding while migrating, feel free to stop it and 
        restart it. I'm saving the progress of migration, so you need not worry
        about reposts.
    """)
    if not os.path.exists('posts.obj'):
        logger.info("Couldn't find serialized object, so parsing the WXR")
        if os.path.exists(WXR):
            posts = parse_wxr(WXR)
            pickle.dump(posts, open(OBJECTFILE, 'w'))
        else:
            logger.critical("Wordpress Archive - %s is not found in this folder" % WXR)
            sys.exit(1)
    else:
        logger.info("Serialized Posts Object found. Loading it")
        posts = pickle.load(open(OBJECTFILE, 'r'))
        
    d = disqus.Api(DISCUSAPIKEY, '1.1')
    if not isinstance(d.get_user_name(), unicode):
        logger.critical("Invalid API Key")
        logger.info("You can get your API KEY @ http://disqus.com/api/get_my_key/")
        sys.exit(1)

    logger.info("Requesting disqus for Forum List")
    f = d.get_forum_list()
    if f is not False:
        logger.info("Received Forum list - %s" % str(f))
        if(len(f) > 1):
            logger.warn("Recieved more than one forum. Hope you changed index in the code")
        logger.info("Requesting Forum API Key for %s" % f[0]['name'])
        fk = d.get_forum_api_key(f[0]['id'])
        # Im just taking the first key for first forum. If you have multiple forums,
        # you might want to edit the index here
        logger.info("Received Forum API Key - %s" % fk)
        d.set_forum_key(fk)
    else:
        logger.critical("Unable to get Forums List")
        sys.exit(1)
    
    for post in posts:
        if not check_progress(post['slug']):
            pattern = re.compile('''(http://YOUR-WORDPRESS-URL\.COM/wp-content/uploads/[\w\_\-\.\/]+)''')
            # Change the pattern for your requirement
            links = list(set(pattern.findall(post['content'])))
            _photo_posts = []
            _attachments = []
            for link in links:
                photo_post = {}
                if link.endswith(".png") or link.endswith(".jpg"):
                    photo_name = link.split("/")[-1].split(".")[0]
                    logger.info("Trying to upload %s to Tumblr as a private post" % photo_name)
                    photo_post_id = post_to_tumblr('photo', photo_name, None, post['date'], None, link, 1)
                    logger.info("Posted %s. Tumblr returned %s" %(photo_name, photo_post_id))
                    photo_post['oldurl'] = link
                    photo_post['name'] = photo_name
                    photo_post['id'] = photo_post_id
                    _photo_posts.append(photo_post)
                    do_wait(5)
                else:
                    _attachments.append(link)
            if len(_attachments) > 0:
                post['attachments'] = _attachments
                logger.warn("Non image attachments were found for '%s'. Upload them manually" % post['title'])
            if len(_photo_posts) > 0:
                post['images'] = _photo_posts
                logger.info("All photos need for the post '%s' are uploaded" % post['title'])
                logger.info("Added the list of images that were uploaded to Tumblr to Primary Posts List")
                do_wait(60, "Tumblr takes awfully long time for providing info of posts just created, So")
        
            for photo_post in _photo_posts:
                post_info = get_post_info(photo_post['id'])
                photo_post['tumblr_info'] = post_info
                photo_post['photo'] = post_info['photo-url-1280']
                logger.info("Replacing all '%s' with '%s'" %(photo_post['oldurl'], photo_post['photo']))
                post['content'] = post['content'].replace(photo_post['oldurl'], photo_post['photo'])
        
            ## Till here, uploaded images needed for the post.
            ## Now, I can do the post
            tumblr_postid = post_to_tumblr('regular', post['title'], post['content'], post['date'], post['tags'])
            post['tumblr_id'] = tumblr_postid
            logger.info("Posted %s to Tumblr with ID - %s" %(post['title'], post['tumblr_id']))
            logger.info("Creating thread for %s @ Disqus" % post['title'])        
            _url = BASEURL + str(post['tumblr_id']) + "/" + post['slug']
            
            if len(post['comments']) > 0:
                t = d.thread_by_identifier(post['tumblr_id'], post['title'])
                d.update_thread(t['thread']['id'],{'title':post['title'], 'slug':post['slug'], 'url':_url, 'allow_comments':'1'})
                logger.info("Updated Thread with Title, Slug and URL for %s" % post['title'])
                logger.info("Updating comments on disqus for %s" % post['title'])
                for comment in post['comments']:
                    m = {}
                    m['thread_id'] = t['thread']['id']
                    m['author_name'] = comment['author']
                    m['author_email'] = comment['author_email']
                    if comment.has_key('a_url'):
                        m['author_url'] = comment['author_url']
                    m['message'] = comment['message']
                    m['ip_address'] = comment['author_ip']
                    m['created_at'] = convert_timestamp_for_disqus(comment['date'])
                    r = d.create_post(m)
                    sys.stdout.write('.')
                    sys.stdout.flush()
            update_progress(post['slug'])
            do_wait(10, "Letting Tumblr breathe for a while before processing next post")
        else:
            logger.info("Post %s already found to be proccessed. Skipping to next one" % post['title'])

    logger.info("Writing the Posts Object after Migration")
    pickle.dump(posts, open('migrated.'+OBJECTFILE, 'w'))
    print("Migration is done. But, few files might not have been migrated. You might have to migrate them manually")
    
    for post in posts:
        if post.has_key('attachments'):
            print("On post - %s I couldn't migrate" % post['title'])
            for a in post['attachments']:
                print(a)
            
def do_wait(stime, reason=None):
    if reason is not None:
        logger.info("\n"+ reason)
    logger.info("... waiting for %s seconds" % stime)
    for i in range(0, stime):
        sys.stdout.write('.')
        time.sleep(1)
        sys.stdout.flush()
    logger.info("  Continuing")

def convert_timestamp_for_disqus(datetime):
    date, time = datetime.split()
    year, mon, day = date.split('-')
    hh, mm, ss = time.split(':')
    return "%s-%s-%sT%s:%s" %(year, mon, day, hh, mm)

def update_progress(post):
    posts = []
    try:
        posts = pickle.load(open(SUCCESSFILE, 'r'))
    except:
        logger.warn("Unable to load successful posts from file - %s" % SUCCESSFILE)
    posts.append(post)
    pickle.dump(posts, open(SUCCESSFILE, 'w'))

def check_progress(title):
    try:
        posts = pickle.load(open(SUCCESSFILE, 'r'))
        if title in posts:
            return True
        else:
            return False
    except:
        return False

def get_post_info(post_id):
    res = do_http_request(TUMBLRREAD, {'email':TUMBLREMAIL, 'password':TUMBLRPASS, 'id':str(post_id)}, 'POST')
    if res is not False:
        logger.info("Extracting Info")
        info = json.loads(res[22:-2])
        if len(info['posts']) > 0:
            logger.info("Extracted!")
            return info['posts'][0]
        else:
            logger.error("Extracted information doesn't contain photo info. Failure")
            logger.debug("Received info from Tumblr - %s" % str(info))
    logger.error("Getting post info failed. Retrying")
    do_wait(30)
    return get_post_info(post_id)

def post_to_tumblr(post_type='regular', title=None, body=None, date=datetime.datetime.now().ctime(), tags=None, source=None, private=0):
    post_data = {
        'email':TUMBLREMAIL,
        'password':TUMBLRPASS,
        'type':post_type,
        'generator':GENERATOR,
        'date':date,
        'title':title
    }
    
    if body is not None:
        post_data['body'] = body

    if source is not None:
        post_data['source'] = source
    
    if private == 1:
        post_data['private'] = '1'
    else:
        post_data['private'] = '0'
    
    if tags is not None:
        post_data['tags'] = ', '.join(tags)
    
    tumblr_post_id = do_http_request(TUMBLRWRITE, post_data, "POST")
    if tumblr_post_id is not False:
        logger.info("Posted %s to Tumblr" %(title))
        return tumblr_post_id

    logger.error("Server acted weird while posting %s" % title)
    do_wait(35)
    return post_to_tumblr(post_type, title, body, date, tags, source, private)

def do_http_request(url, post_data={}, method="GET"):
    params = urllib.urlencode(dict([k, v.encode('utf-8')] for k, v in post_data.items()))
    if method == "POST":
        request = urllib2.Request(url, params)
    else:
        if len(post_data) > 0:
            url = url + '?' + params
        request = urllib2.Request(url)
    try:
        logger.debug("Requesting %s using HTTP %s with data %s" %(url, method, str(post_data)))
        response = urllib2.urlopen(request)
        return response.read()
    except Exception, e:
        logger.error("Error requesting %s using HTTP %s with data %s with Exception %s" %(url, method, str(post_data), e))
        return False

def parse_wxr(wxr):
    posts = []
    import xml.dom.minidom
    from xml.dom.minidom import Node
    doc = xml.dom.minidom.parse(wxr)
    items = doc.getElementsByTagName("item")
    logger.info("Total Number of Entries (posts, pages and attachments) in the Wordpress eXtended Rss file : %s" %(len(items)))
    for post in items:
        _post = {}
        if post.getElementsByTagName("wp:post_type")[0].firstChild.data == "post":
            _post['title'] = post.getElementsByTagName("title")[0].firstChild.data
            _post['slug'] = post.getElementsByTagName("wp:post_name")[0].firstChild.data
            _post['link'] = post.getElementsByTagName("link")[0].firstChild.data
            _post['date'] = post.getElementsByTagName("wp:post_date")[0].firstChild.data
            _post['content'] = post.getElementsByTagName("content:encoded")[0].firstChild.data
            _post['tags'] = list()
            terms = post.getElementsByTagName("category")
            for term in terms:
                if term.getAttribute("domain") == "tag" and term.getAttribute("nicename") != "":
                    _post['tags'].append(term.firstChild.data)
            
            comments = post.getElementsByTagName("wp:comment")
            _post['comments'] = list()
            for comment in comments:
                _comment = {}
                _comment['date'] = comment.getElementsByTagName("wp:comment_date")[0].firstChild.data
                if comment.getElementsByTagName("wp:comment_author")[0].hasChildNodes():
                    _comment['author'] = comment.getElementsByTagName("wp:comment_author")[0].firstChild.data
                else:
                    _comment['author'] = "Anonymous"
                if comment.getElementsByTagName("wp:comment_author_email")[0].hasChildNodes():
                    _comment['author_email'] = comment.getElementsByTagName("wp:comment_author_email")[0].firstChild.data
                else:
                    _comment['author_email'] = "anonymous@anonymous.com"
                if comment.getElementsByTagName("wp:comment_author_url")[0].hasChildNodes():
                    _comment['author_url'] = comment.getElementsByTagName("wp:comment_author_url")[0].firstChild.data
                else:
                    _comment['author_url'] = "http://www.google.com"
                if comment.getElementsByTagName("wp:comment_author_IP")[0].hasChildNodes():
                    _comment['author_ip'] = comment.getElementsByTagName("wp:comment_author_IP")[0].firstChild.data
                else:
                    _comment['author_ip'] = "127.0.0.1"
                _comment['message'] = comment.getElementsByTagName("wp:comment_content")[0].firstChild.data
                _post['comments'].append(_comment)
            posts.append(_post)
    logger.info("Finished parsing WXR. Returning the Posts")
    return posts

if __name__ == '__main__':
    main()
