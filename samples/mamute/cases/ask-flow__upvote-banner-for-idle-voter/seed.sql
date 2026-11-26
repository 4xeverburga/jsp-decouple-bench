-- The seeded moderator last upvoted long ago, as any user who has not voted
-- for a week: isVotingEnough() is false, so the question page asks for an
-- upvote. It is the only user at first boot (DefaultAdminCreator), id 1001.
UPDATE `Users` SET `lastUpvote` = '2017-01-01 00:00:00' WHERE `id` = 1001;
