-- Nine teachers beyond the dump's four: thirteen rows, a second page of
-- three. Ids continue userlogin's AUTO_INCREMENT; a teacher's id is its
-- login's.
INSERT INTO `userlogin` (`id`, `name`, `password`, `role`) VALUES
  (41, '王老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (42, '陈老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (43, '杨老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (44, '赵老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (45, '孙老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (46, '马老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (47, '黄老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (48, '周老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2),
  (49, '吴老师', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 2);
INSERT INTO `teacher` (`id`, `name`, `sex`, `birthday`, `degree`, `register_time`) VALUES
  (41, '王老师', '男', '1975-03-12', '博士', '2017-11-06'),
  (42, '陈老师', '女', '1982-07-21', '硕士', '2017-11-06'),
  (43, '杨老师', '男', '1979-11-02', '本科', '2017-11-07'),
  (44, '赵老师', '女', '1988-01-30', '硕士', '2017-11-07'),
  (45, '孙老师', '男', '1970-09-14', '博士', '2017-11-08'),
  (46, '马老师', '女', '1985-04-05', '本科', '2017-11-08'),
  (47, '黄老师', '男', '1977-12-19', '博士', '2017-11-09'),
  (48, '周老师', '女', '1990-06-08', '硕士', '2017-11-09'),
  (49, '吴老师', '男', '1983-02-27', '本科', '2017-11-10');
