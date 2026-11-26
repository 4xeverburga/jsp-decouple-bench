-- Eight courses beyond the dump's four: twelve rows, a second page of two.
-- Ids continue the dump's AUTO_INCREMENT; teachers are the dump's own.
INSERT INTO `course` (`id`, `name`, `teacher_id`, `period`, `price`) VALUES
  (9, '数据结构', 25, 32, 15),
  (10, '操作系统', 26, 40, 18),
  (11, '计算机网络', 37, 36, 16),
  (12, '数据库原理', 25, 30, 12),
  (13, '编译原理', 26, 48, 22),
  (14, '离散数学', 37, 28, 8),
  (15, '软件工程', 25, 24, 14),
  (16, '线性代数', 26, 34, 9);
