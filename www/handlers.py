#!/usr/bin/env python3
# -*- coding: utf-8 -*-
' url handlers '
import hashlib
import json
import logging
import re
import time

import markdown2 as markdown2
from aiohttp import web

from www.apis import APIValueError, APIError, APIPermissionError, Page
from www.config_default import configs
from www.coroweb import get, post
from www.model import User, Blog, next_id,Comment
from www.user_email import send_user_email

COOKIE_NAME='awesession'
_COOKIE_KEY=configs['session']['secret']

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)
def user2cookie(user, max_age):
    '''
    Generate cookie str by user
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    '''
     Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

@get('/blog_list')
async def blog_list(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index, page_size=5)
    if num == 0:
        return dict(page=p, blogs=())
    else:
        blogs = await Blog.findall(orderBy='created_at desc ', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

@get('/')
def list_blog(* ,page='1'):
    return{
        '__template__': 'blogs.html',
        'page_index': get_page_index(page)
    }

@get('/blog/{id}')
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findall('blog_id', [id],orderBy='created_at desc' )
    for c in comments:
        # c.html_content = text2html(c.content)
        c.html_content = c.content
    # blog.html_content = markdown2.markdown(blog.content)
    blog.html_content = blog.content
    return {
        '__template__':'blog.html',
        'blog':blog,
        'comments':comments
    }

@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }

@get('/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }

@get('/manage/users')
def manage_users(*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }

@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__':'manage_blog_edit.html',
        'id':'',
        'action':'/api/blogs'
    }

@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
    return {
        '__template__':'manage_blog_edit.html',
        'id': id,
        'action':'/api/blogs/%s' % id
    }

@get('/register')
def register():
    return {
        '__template__':'register.html'
    }

@get('/signin')
def signin():
    return {
        '__template__':'signin.html'
    }

@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email')
    if not passwd:
        raise APIValueError('passwd', 'Invalid passwd')
    users = await User.findall('email',[email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check passwd
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid passwd')
    # authenticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400),max_age=86400,httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
    return r

@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/manage/')
def manage():
    return 'redirect:/manage/comments'


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/users')
async def api_register_users(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findall('email', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use')
    send_user_email(email,name,passwd)
    return dict(r='yes')
    #
    # uid = next_id()
    # sha1_passwd = '%s:%s' % (uid, passwd)
    # user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
    #             image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    # await user.save()
    # # make session cookie
    # r = web.Response()
    # r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    # user.passwd = '******'
    # r.content_type = 'application/json'
    # r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
    # return r

@get('/api/user_yes')
async def user_yes(request,* ,name, em, mm, t):
    '''
    邮箱验证注册
    :param request:
    :param name:
    :param em:
    :param mm:
    :return:
    '''
    if float(time.time())-float(t)>1800:
        return 'redirect:/'
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, mm)
    user = User(id=uid, name=name.strip(), email=em, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(em.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return 'redirect:/'


@get('/api/users')
async def api_users(*, page='1'):
    '''
    分页查询用户
    :param page:
    :return:
    '''
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findall(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)

@get('/api/blogs')
async def api_blogs(*, page='1'):
    '''
    根据页码查询日志，默认一页10条，初始页码为1
    如果没有日志返回空dict
    :param page:
    :return:
    '''
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findall(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

@get('/api/comments')
async def api_comments(*, page=1):
    '''
    分页查询评论
    :param page:
    :return:
    '''
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num ==0:
        return dict(page=p, comments=())
    comments = await Comment.findall(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)

@post('/api/blogs/{id}/comments')
async def api_create_comments(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = await Blog.find(id)
    if blog is None:
        raise APIValueError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    await comment.save()
    return comment

@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    check_admin(request)
    c = await Comment.find(id)
    if c is None:
        raise APIValueError('Comment')
    await c.remove()
    return dict(id=id)

@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

@post('/api/blogs/{id}')
async def api_update_blogs(id, request, *, name, summary, content):
    '''
    日志修改
    :param request: 请求
    :param id: 日志Id
    :param name: 标题
    :param summary: 摘要
    :param content: 内容
    :return:
    '''
    blog = await Blog.find(id)
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog

@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,
                name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog

@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
    check_admin(request)
    blog = await Blog.find(id)
    comment = await Comment.findall('blog_id',[id])
    if len(comment) >0:
        for cm in comment:
            await cm.remove()
    await blog.remove()
    return dict(id=id)

@get('/user/{id}')
async def user_info(id):
    user = await User.find(id)
    print(user)
    return {
        '__template__': 'user_info.html',
        'user': user
    }
