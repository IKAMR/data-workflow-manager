# a15.6.1

This increment fixes two small usability gaps:

- The main window now saves whether it was actually maximized (`zoomed`) at close
  and restores that state after GUI initialization when Setup allows it.
- The active job now has a `Standard` action in the main header. It applies the
  configured storage-layout profile and Noark 5 workflow after confirmation.

Existing result files are not deleted.
