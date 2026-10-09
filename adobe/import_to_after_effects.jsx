// File > Scripts > Run Script File... (Adobe After Effects)
(function () {
  app.beginUndoGroup('ZAX Auto Editor Import');
  var file = File.openDialog('Choose a video rendered by ZAX Auto Editor');
  if (file && file.exists) {
    if (!app.project) app.newProject();
    var item = app.project.importFile(new ImportOptions(file));
    var comp = app.project.items.addComp('ZAX - ' + item.name, item.width, item.height, 1, item.duration, item.frameRate || 30);
    comp.layers.add(item);
    comp.openInViewer();
  }
  app.endUndoGroup();
})();
