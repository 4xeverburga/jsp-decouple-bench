-- The seeded moderator has been downvoted below zero: hasKarma() is false,
-- so an answer earns it nothing. It is the only user at first boot
-- (DefaultAdminCreator), id 1001.
UPDATE `Users` SET `karma` = -5 WHERE `id` = 1001;
