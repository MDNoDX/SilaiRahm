"""Pages of the family archive, one module per topic.

    people      relatives: list, person page, add / edit / delete, marriages
    album       photos, documents and recordings of a person
    tree        the family tree, fan chart, quick add, PDFs, the family book
    timeline    the family's years in order
    events      family events and upcoming dates
    stories     family stories
    search      search page and live search
    calculator  "who is who to whom?"
    changes     duplicates, merging, history of changes and undo
    exchange    GEDCOM and JSON export / import

urls.py reaches every page through this package (views.people_list, …).
"""
from .people import (
    marriage_edit, people_list, person_create, person_delete, person_detail, person_edit, person_pdf, relative_add,
    set_self,
)
from .album import media_delete, media_portrait, media_upload
from .changes import duplicates_page, history_page, history_undo, merge_people
from .tree import book_page, family_book, fan_data, person_card, quick_add, tree_data, tree_page, tree_pdf
from .timeline import timeline
from .stories import story_create, story_delete, story_detail, story_edit, story_list
from .search import search, search_json
from .events import event_create, event_delete, event_detail, event_edit, upcoming
from .calculator import calculator
from .exchange import archive_export, gedcom_export, gedcom_import
