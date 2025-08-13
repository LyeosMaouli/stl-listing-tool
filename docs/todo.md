## Fixes

- [ ] Resolve warnings (vtk_renderer, error_dialog, ...)

## Improvements

- [ ] Folder import
- [ ] Queue
- [x] Change rendered saved image path from C:\Users\user\AppData\Local\Temp\stl_render.png to project folder ./tmp
- [x] Custom Background
- [ ] Size chart
- [ ] Add "podium"
- [x] Save settings
- [ ] Move ./batch_queue_state to ~/.local/stl_listing_tool/
- [ ] Move all changing folders to `~/.local/stl_listing_tool/

## Cleanup

- [ ] Remove debugging code

## Next step

I want to add a queue system for the render where :

- All imported stl files are listed
- The process should be :
  1. Select one or multiple STL files, or a folder (then the program look for STL files recursivly)
  2. Select what we want to render with multiple selection with check boxes (render options: image, size chart, video presentation, Color varations), the validation check dropdown, and the custom background.
  3. Select the output folder
- When launched, we have a queue position system
- Then the queue validate all files, all the non proper ones wille be skipped for next steps
- After, it render all the things selected previously for each file, with it own subfolder for each STL file
- Finally, it checks if nothing is missing
  We should also be able to pause, resume, stop and restart the queue.
  The full queue and its position should be saved uppon quitting for next time.
