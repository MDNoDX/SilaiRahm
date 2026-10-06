
'use strict';
{
  const globals = this;
  const django = globals.django || (globals.django = {});

  
  django.pluralidx = function(n) {
    const v = 0;
    if (typeof v === 'boolean') {
      return v ? 1 : 0;
    } else {
      return v;
    }
  };
  

  /* gettext library */

  django.catalog = django.catalog || {};
  
  const newcatalog = {
    "Add father": "\u041e\u0442\u0430\u0441\u0438\u043d\u0438 \u049b\u045e\u0448\u0438\u0448",
    "Add mother": "\u041e\u043d\u0430\u0441\u0438\u043d\u0438 \u049b\u045e\u0448\u0438\u0448",
    "An error occurred.": "\u0425\u0430\u0442\u043e\u043b\u0438\u043a \u044e\u0437 \u0431\u0435\u0440\u0434\u0438.",
    "Are you sure you want to delete this?": "\u0420\u043e\u0441\u0442\u0434\u0430\u043d \u04b3\u0430\u043c \u045e\u0447\u0438\u0440\u043c\u043e\u049b\u0447\u0438\u043c\u0438\u0441\u0438\u0437?",
    "Automatic": "\u0410\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u043a",
    "Blocked in the browser settings": "\u0411\u0440\u0430\u0443\u0437\u0435\u0440 \u0441\u043e\u0437\u043b\u0430\u043c\u0430\u043b\u0430\u0440\u0438\u0434\u0430 \u0431\u043b\u043e\u043a\u043b\u0430\u043d\u0433\u0430\u043d",
    "Choose a file": "\u0424\u0430\u0439\u043b \u0442\u0430\u043d\u043b\u0430\u0448",
    "Close": "\u0401\u043f\u0438\u0448",
    "Colour theme": "\u0420\u0430\u043d\u0433 \u043c\u0430\u0432\u0437\u0443\u0441\u0438",
    "Copied": "\u041d\u0443\u0441\u0445\u0430\u043b\u0430\u043d\u0434\u0438",
    "Could not load the family tree. Please try again.": "\u0428\u0430\u0436\u0430\u0440\u0430\u043d\u0438 \u044e\u043a\u043b\u0430\u0431 \u0431\u045e\u043b\u043c\u0430\u0434\u0438. \u049a\u0430\u0439\u0442\u0430\u0434\u0430\u043d \u0443\u0440\u0438\u043d\u0438\u0431 \u043a\u045e\u0440\u0438\u043d\u0433.",
    "Dark": "\u049a\u043e\u0440\u043e\u043d\u0493\u0438",
    "Family tree": "\u0428\u0430\u0436\u0430\u0440\u0430",
    "Hide brothers and sisters": "\u0410\u043a\u0430-\u0443\u043a\u0430 \u0432\u0430 \u043e\u043f\u0430-\u0441\u0438\u043d\u0433\u0438\u043b\u043b\u0430\u0440\u0438\u043d\u0438 \u044f\u0448\u0438\u0440\u0438\u0448",
    "Hide children": "\u0424\u0430\u0440\u0437\u0430\u043d\u0434\u043b\u0430\u0440\u0438\u043d\u0438 \u044f\u0448\u0438\u0440\u0438\u0448",
    "Light": "\u0401\u0440\u0443\u0493",
    "No file chosen": "\u0424\u0430\u0439\u043b \u0442\u0430\u043d\u043b\u0430\u043d\u043c\u0430\u0433\u0430\u043d",
    "No results found.": "\u049a\u0438\u0434\u0438\u0440\u0443\u0432 \u043d\u0430\u0442\u0438\u0436\u0430\u0441\u0438 \u0442\u043e\u043f\u0438\u043b\u043c\u0430\u0434\u0438.",
    "Off for this device": "\u0411\u0443 \u049b\u0443\u0440\u0438\u043b\u043c\u0430\u0434\u0430 \u045e\u0447\u0438\u0440\u0438\u043b\u0433\u0430\u043d",
    "On for this device": "\u0411\u0443 \u049b\u0443\u0440\u0438\u043b\u043c\u0430\u0434\u0430 \u0451\u049b\u0438\u043b\u0433\u0430\u043d",
    "Saving\u2026": "\u0421\u0430\u049b\u043b\u0430\u043d\u043c\u043e\u049b\u0434\u0430\u2026",
    "Show brothers and sisters": "\u0410\u043a\u0430-\u0443\u043a\u0430 \u0432\u0430 \u043e\u043f\u0430-\u0441\u0438\u043d\u0433\u0438\u043b\u043b\u0430\u0440\u0438\u043d\u0438 \u043a\u045e\u0440\u0441\u0430\u0442\u0438\u0448",
    "Show children": "\u0424\u0430\u0440\u0437\u0430\u043d\u0434\u043b\u0430\u0440\u0438\u043d\u0438 \u043a\u045e\u0440\u0441\u0430\u0442\u0438\u0448",
    "The family tree is empty.": "\u0428\u0430\u0436\u0430\u0440\u0430 \u04b3\u0430\u043b\u0438 \u0431\u045e\u0448.",
    "The photo is too large. The maximum size is %(size)s MB.": "\u0420\u0430\u0441\u043c \u04b3\u0430\u0436\u043c\u0438 \u0436\u0443\u0434\u0430 \u043a\u0430\u0442\u0442\u0430. \u042d\u043d\u0433 \u043a\u045e\u043f\u0438 %(size)s \u041c\u0411 \u0431\u045e\u043b\u0438\u0448\u0438 \u043c\u0443\u043c\u043a\u0438\u043d.",
    "Type a name to filter\u2026": "\u0418\u0441\u043c\u043d\u0438 \u0451\u0437\u0438\u0431 \u049b\u0438\u0434\u0438\u0440\u0438\u043d\u0433\u2026",
    "You": "\u0421\u0438\u0437",
    "file name\u0004family-tree": "\u0448\u0430\u0436\u0430\u0440\u0430"
  };
  for (const key in newcatalog) {
    django.catalog[key] = newcatalog[key];
  }
  

  if (!django.jsi18n_initialized) {
    django.gettext = function(msgid) {
      const value = django.catalog[msgid];
      if (typeof value === 'undefined') {
        return msgid;
      } else {
        return (typeof value === 'string') ? value : value[0];
      }
    };

    django.ngettext = function(singular, plural, count) {
      const value = django.catalog[singular];
      if (typeof value === 'undefined') {
        return (count == 1) ? singular : plural;
      } else {
        return value.constructor === Array ? value[django.pluralidx(count)] : value;
      }
    };

    django.gettext_noop = function(msgid) { return msgid; };

    django.pgettext = function(context, msgid) {
      let value = django.gettext(context + '\x04' + msgid);
      if (value.includes('\x04')) {
        value = msgid;
      }
      return value;
    };

    django.npgettext = function(context, singular, plural, count) {
      let value = django.ngettext(context + '\x04' + singular, context + '\x04' + plural, count);
      if (value.includes('\x04')) {
        value = django.ngettext(singular, plural, count);
      }
      return value;
    };

    django.interpolate = function(fmt, obj, named) {
      if (named) {
        return fmt.replace(/%\(\w+\)s/g, function(match){return String(obj[match.slice(2,-2)])});
      } else {
        return fmt.replace(/%s/g, function(match){return String(obj.shift())});
      }
    };


    /* formatting library */

    django.formats = {
    "DATETIME_FORMAT": "Y \\\u0439\\\u0438\\\u043b j E, H:i",
    "DATETIME_INPUT_FORMATS": [
      "%d.%m.%Y %H:%M:%S",
      "%d.%m.%Y %H:%M:%S.%f",
      "%d.%m.%Y %H:%M",
      "%d-%B, %Y-yil %H:%M:%S",
      "%d-%B, %Y-yil %H:%M:%S.%f",
      "%d-%B, %Y-yil %H:%M",
      "%Y-%m-%d %H:%M:%S",
      "%Y-%m-%d %H:%M:%S.%f",
      "%Y-%m-%d %H:%M",
      "%Y-%m-%d"
    ],
    "DATE_FORMAT": "Y \\\u0439\\\u0438\\\u043b j E",
    "DATE_INPUT_FORMATS": [
      "%d.%m.%Y",
      "%Y-%m-%d"
    ],
    "DECIMAL_SEPARATOR": ",",
    "FIRST_DAY_OF_WEEK": 1,
    "MONTH_DAY_FORMAT": "j E",
    "NUMBER_GROUPING": 3,
    "SHORT_DATETIME_FORMAT": "d.m.Y H:i",
    "SHORT_DATE_FORMAT": "d.m.Y",
    "THOUSAND_SEPARATOR": "\u00a0",
    "TIME_FORMAT": "H:i",
    "TIME_INPUT_FORMATS": [
      "%H:%M:%S",
      "%H:%M:%S.%f",
      "%H:%M"
    ],
    "YEAR_MONTH_FORMAT": "Y \\\u0439\\\u0438\\\u043b F"
  };

    django.get_format = function(format_type) {
      const value = django.formats[format_type];
      if (typeof value === 'undefined') {
        return format_type;
      } else {
        return value;
      }
    };

    /* add to global namespace */
    globals.pluralidx = django.pluralidx;
    globals.gettext = django.gettext;
    globals.ngettext = django.ngettext;
    globals.gettext_noop = django.gettext_noop;
    globals.pgettext = django.pgettext;
    globals.npgettext = django.npgettext;
    globals.interpolate = django.interpolate;
    globals.get_format = django.get_format;

    django.jsi18n_initialized = true;
  }
};

