
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
    "Add father": "Otasini qo\u02bbshish",
    "Add mother": "Onasini qo\u02bbshish",
    "An error occurred.": "Xatolik yuz berdi.",
    "Are you sure you want to delete this?": "Rostdan ham o\u02bbchirmoqchimisiz?",
    "Automatic": "Avtomatik",
    "Blocked in the browser settings": "Brauzer sozlamalarida bloklangan",
    "Choose a file": "Fayl tanlash",
    "Close": "Yopish",
    "Colour theme": "Rang mavzusi",
    "Copied": "Nusxalandi",
    "Could not load the family tree. Please try again.": "Shajarani yuklab bo\u02bblmadi. Qaytadan urinib ko\u02bbring.",
    "Dark": "Qorong\u02bbi",
    "Family tree": "Shajara",
    "Hide brothers and sisters": "Aka-uka va opa-singillarini yashirish",
    "Hide children": "Farzandlarini yashirish",
    "Light": "Yorug\u02bb",
    "No file chosen": "Fayl tanlanmagan",
    "No results found.": "Qidiruv natijasi topilmadi.",
    "Off for this device": "Bu qurilmada o\u02bbchirilgan",
    "On for this device": "Bu qurilmada yoqilgan",
    "Saving\u2026": "Saqlanmoqda\u2026",
    "Show brothers and sisters": "Aka-uka va opa-singillarini ko\u02bbrsatish",
    "Show children": "Farzandlarini ko\u02bbrsatish",
    "The family tree is empty.": "Shajara hali bo\u02bbsh.",
    "The photo is too large. The maximum size is %(size)s MB.": "Rasm hajmi juda katta. Eng ko\u02bbpi %(size)s MB bo\u02bblishi mumkin.",
    "Type a name to filter\u2026": "Ismni yozib qidiring\u2026",
    "You": "Siz",
    "file name\u0004family-tree": "shajara"
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
    "DATETIME_FORMAT": "j-E Y-\\y\\i\\l, H:i",
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
    "DATE_FORMAT": "j-E Y-\\y\\i\\l",
    "DATE_INPUT_FORMATS": [
      "%d.%m.%Y",
      "%Y-%m-%d"
    ],
    "DECIMAL_SEPARATOR": ",",
    "FIRST_DAY_OF_WEEK": 1,
    "MONTH_DAY_FORMAT": "j-E",
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
    "YEAR_MONTH_FORMAT": "Y-\\y\\i\\l F"
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

