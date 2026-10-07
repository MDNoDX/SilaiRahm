
'use strict';
{
  const globals = this;
  const django = globals.django || (globals.django = {});

  
  django.pluralidx = function(n) {
    const v = (n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);
    if (typeof v === 'boolean') {
      return v ? 1 : 0;
    } else {
      return v;
    }
  };
  

  /* gettext library */

  django.catalog = django.catalog || {};
  
  const newcatalog = {
    "Add": "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c",
    "Also write it down as text": "\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0442\u0430\u043a\u0436\u0435 \u0442\u0435\u043a\u0441\u0442\u043e\u043c",
    "An error occurred.": "\u041f\u0440\u043e\u0438\u0437\u043e\u0448\u043b\u0430 \u043e\u0448\u0438\u0431\u043a\u0430.",
    "Are you sure you want to delete this?": "\u0412\u044b \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u044c\u043d\u043e \u0445\u043e\u0442\u0438\u0442\u0435 \u0443\u0434\u0430\u043b\u0438\u0442\u044c?",
    "Automatic": "\u041a\u0430\u043a \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0435",
    "Blocked in the browser settings": "\u0417\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u043e \u0432 \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430\u0445 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0430",
    "Choose a file": "\u0412\u044b\u0431\u0440\u0430\u0442\u044c \u0444\u0430\u0439\u043b",
    "Close": "\u0417\u0430\u043a\u0440\u044b\u0442\u044c",
    "Colour theme": "\u0422\u0435\u043c\u0430",
    "Copied": "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u043e",
    "Could not load the family tree. Please try again.": "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0434\u0440\u0435\u0432\u043e. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.",
    "Dark": "\u0422\u0451\u043c\u043d\u0430\u044f",
    "Edit": "\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c",
    "Family tree": "\u0420\u043e\u0434\u043e\u0441\u043b\u043e\u0432\u043d\u043e\u0435 \u0434\u0440\u0435\u0432\u043e",
    "For example: Grandfather tells about his childhood": "\u041d\u0430\u043f\u0440\u0438\u043c\u0435\u0440: \u0434\u0435\u0434\u0443\u0448\u043a\u0430 \u0440\u0430\u0441\u0441\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442 \u043e \u0434\u0435\u0442\u0441\u0442\u0432\u0435",
    "Hide brothers and sisters": "\u0421\u043a\u0440\u044b\u0442\u044c \u0431\u0440\u0430\u0442\u044c\u0435\u0432 \u0438 \u0441\u0435\u0441\u0442\u0451\u0440",
    "Hide children": "\u0421\u043a\u0440\u044b\u0442\u044c \u0434\u0435\u0442\u0435\u0439",
    "Light": "\u0421\u0432\u0435\u0442\u043b\u0430\u044f",
    "No connection. Check the internet and try again.": "\u041d\u0435\u0442 \u0441\u0432\u044f\u0437\u0438. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0438\u043d\u0442\u0435\u0440\u043d\u0435\u0442 \u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.",
    "No file chosen": "\u0424\u0430\u0439\u043b \u043d\u0435 \u0432\u044b\u0431\u0440\u0430\u043d",
    "No results found.": "\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e.",
    "No, thanks": "\u041d\u0435\u0442, \u0441\u043f\u0430\u0441\u0438\u0431\u043e",
    "Not saved": "\u041d\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e",
    "Off for this device": "\u041d\u0430 \u044d\u0442\u043e\u043c \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0435 \u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d\u043e",
    "On for this device": "\u041d\u0430 \u044d\u0442\u043e\u043c \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0435 \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u043e",
    "Open": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c",
    "Proposed": "\u041f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u043e",
    "Remove": "\u0423\u0434\u0430\u043b\u0438\u0442\u044c",
    "Save as an event": "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043a\u0430\u043a \u0441\u043e\u0431\u044b\u0442\u0438\u0435",
    "Saved": "\u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e",
    "Saving\u2026": "\u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435\u2026",
    "Show brothers and sisters": "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0431\u0440\u0430\u0442\u044c\u0435\u0432 \u0438 \u0441\u0435\u0441\u0442\u0451\u0440",
    "Show children": "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0434\u0435\u0442\u0435\u0439",
    "Something went wrong. Please try again.": "\u0427\u0442\u043e-\u0442\u043e \u043f\u043e\u0448\u043b\u043e \u043d\u0435 \u0442\u0430\u043a. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.",
    "The camera could not be turned on. Allow access to the camera and the microphone in the browser.": "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043a\u0430\u043c\u0435\u0440\u0443. \u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u043a\u0430\u043c\u0435\u0440\u0435 \u0438 \u043c\u0438\u043a\u0440\u043e\u0444\u043e\u043d\u0443 \u0432 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435.",
    "The family tree is empty.": "\u0414\u0440\u0435\u0432\u043e \u043f\u043e\u043a\u0430 \u043f\u0443\u0441\u0442\u043e\u0435.",
    "The microphone could not be turned on. Allow access to the microphone in the browser.": "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043c\u0438\u043a\u0440\u043e\u0444\u043e\u043d. \u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u0435 \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u043c\u0438\u043a\u0440\u043e\u0444\u043e\u043d\u0443 \u0432 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435.",
    "The photo is too large. The maximum size is %(size)s MB.": "\u0424\u043e\u0442\u043e \u0441\u043b\u0438\u0448\u043a\u043e\u043c \u0431\u043e\u043b\u044c\u0448\u043e\u0435. \u041c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439 \u0440\u0430\u0437\u043c\u0435\u0440 \u2014 %(size)s \u041c\u0411.",
    "The recording is too long: up to 4 MB (about 25 minutes of voice or 1 minute of video).": "\u0417\u0430\u043f\u0438\u0441\u044c \u0441\u043b\u0438\u0448\u043a\u043e\u043c \u0434\u043b\u0438\u043d\u043d\u0430\u044f: \u0434\u043e 4 MB (\u043f\u0440\u0438\u043c\u0435\u0440\u043d\u043e 25 \u043c\u0438\u043d\u0443\u0442 \u0433\u043e\u043b\u043e\u0441\u0430 \u0438\u043b\u0438 1 \u043c\u0438\u043d\u0443\u0442\u0430 \u0432\u0438\u0434\u0435\u043e).",
    "This browser cannot attach the recording. Choose a recorded file instead.": "\u042d\u0442\u043e\u0442 \u0431\u0440\u0430\u0443\u0437\u0435\u0440 \u043d\u0435 \u043c\u043e\u0436\u0435\u0442 \u043f\u0440\u0438\u043a\u0440\u0435\u043f\u0438\u0442\u044c \u0437\u0430\u043f\u0438\u0441\u044c. \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0437\u0430\u043f\u0438\u0441\u0430\u043d\u043d\u044b\u0439 \u0444\u0430\u0439\u043b.",
    "Title": "\u0417\u0430\u0433\u043e\u043b\u043e\u0432\u043e\u043a",
    "Turn into text and send": "\u041f\u0440\u0435\u0432\u0440\u0430\u0442\u0438\u0442\u044c \u0432 \u0442\u0435\u043a\u0441\u0442 \u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c",
    "Write a title for the recording.": "\u041d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0437\u0430\u0433\u043e\u043b\u043e\u0432\u043e\u043a \u0434\u043b\u044f \u0437\u0430\u043f\u0438\u0441\u0438.",
    "Writing it down\u2026": "\u0417\u0430\u043f\u0438\u0441\u044b\u0432\u0430\u044e \u0442\u0435\u043a\u0441\u0442\u043e\u043c\u2026",
    "You": "\u0412\u044b",
    "file name\u0004family-tree": "\u0448\u0430\u0434\u0436\u0430\u0440\u0430"
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
    "DATETIME_FORMAT": "j E Y \u0433. G:i",
    "DATETIME_INPUT_FORMATS": [
      "%d.%m.%Y %H:%M:%S",
      "%d.%m.%Y %H:%M:%S.%f",
      "%d.%m.%Y %H:%M",
      "%d.%m.%y %H:%M:%S",
      "%d.%m.%y %H:%M:%S.%f",
      "%d.%m.%y %H:%M",
      "%Y-%m-%d %H:%M:%S",
      "%Y-%m-%d %H:%M:%S.%f",
      "%Y-%m-%d %H:%M",
      "%Y-%m-%d"
    ],
    "DATE_FORMAT": "j E Y \u0433.",
    "DATE_INPUT_FORMATS": [
      "%d.%m.%Y",
      "%d.%m.%y",
      "%Y-%m-%d"
    ],
    "DECIMAL_SEPARATOR": ",",
    "FIRST_DAY_OF_WEEK": 1,
    "MONTH_DAY_FORMAT": "j F",
    "NUMBER_GROUPING": 3,
    "SHORT_DATETIME_FORMAT": "d.m.Y H:i",
    "SHORT_DATE_FORMAT": "d.m.Y",
    "THOUSAND_SEPARATOR": "\u00a0",
    "TIME_FORMAT": "G:i",
    "TIME_INPUT_FORMATS": [
      "%H:%M:%S",
      "%H:%M:%S.%f",
      "%H:%M"
    ],
    "YEAR_MONTH_FORMAT": "F Y \u0433."
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

