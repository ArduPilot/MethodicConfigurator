import gettext


# Setup language
locale_path = 'locale'  # directory of locale file
language = 'zh_CN'  # select language

# create translation
translation = gettext.translation('messages', localedir=locale_path, languages=[language], fallback=True)

# set translation object as _()
_ = translation.gettext


