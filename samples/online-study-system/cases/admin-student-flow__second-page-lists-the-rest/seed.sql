-- Nine students beyond the dump's three: twelve rows, a second page of two.
-- Ids continue userlogin's AUTO_INCREMENT; a student's id is its login's.
INSERT INTO `userlogin` (`id`, `name`, `password`, `role`) VALUES
  (41, '小王', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (42, '小李', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (43, '小张', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (44, '小刘', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (45, '小陈', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (46, '小杨', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (47, '小赵', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (48, '小黄', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3),
  (49, '小周', 'b2d1f375db625e65a4a63ba0c7b29bdd738392cd83c38b8216c10c4d', 3);
INSERT INTO `student` (`id`, `name`, `sex`, `birthday`, `register_time`, `balance`) VALUES
  (41, '小王', '男', '1996-03-12', '2017-11-06', 20),
  (42, '小李', '女', '1997-07-21', '2017-11-06', 0),
  (43, '小张', '男', '1995-11-02', '2017-11-07', 35),
  (44, '小刘', '女', '1998-01-30', '2017-11-07', 0),
  (45, '小陈', '男', '1996-09-14', '2017-11-08', 10),
  (46, '小杨', '女', '1997-04-05', '2017-11-08', 0),
  (47, '小赵', '男', '1995-12-19', '2017-11-09', 50),
  (48, '小黄', '女', '1998-06-08', '2017-11-09', 5),
  (49, '小周', '男', '1996-02-27', '2017-11-10', 0);
