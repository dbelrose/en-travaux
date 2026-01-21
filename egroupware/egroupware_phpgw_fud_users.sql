-- MySQL dump 10.13  Distrib 8.0.31, for Win64 (x86_64)
--
-- Host: dbpnf.srv.gov.pf    Database: egroupware
-- ------------------------------------------------------
-- Server version	5.5.43-0+deb7u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `phpgw_fud_users`
--

DROP TABLE IF EXISTS `phpgw_fud_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `phpgw_fud_users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `login` varchar(50) DEFAULT NULL,
  `alias` varchar(50) DEFAULT NULL,
  `passwd` varchar(32) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `location` varchar(255) DEFAULT NULL,
  `interests` varchar(255) DEFAULT NULL,
  `occupation` varchar(255) DEFAULT NULL,
  `avatar` int(11) NOT NULL DEFAULT '0',
  `avatar_loc` text,
  `icq` bigint(20) DEFAULT NULL,
  `aim` varchar(255) DEFAULT NULL,
  `yahoo` varchar(255) DEFAULT NULL,
  `msnm` varchar(255) DEFAULT NULL,
  `jabber` varchar(255) DEFAULT NULL,
  `affero` varchar(255) DEFAULT NULL,
  `posts_ppg` int(11) NOT NULL DEFAULT '0',
  `time_zone` varchar(255) NOT NULL DEFAULT 'America/Montreal',
  `bday` int(11) NOT NULL DEFAULT '0',
  `join_date` bigint(20) NOT NULL DEFAULT '0',
  `conf_key` varchar(32) NOT NULL DEFAULT '0',
  `user_image` varchar(255) DEFAULT NULL,
  `theme` int(11) NOT NULL DEFAULT '0',
  `posted_msg_count` int(11) NOT NULL DEFAULT '0',
  `last_visit` bigint(20) NOT NULL DEFAULT '0',
  `referer_id` int(11) NOT NULL DEFAULT '0',
  `last_read` bigint(20) NOT NULL DEFAULT '0',
  `custom_status` text,
  `sig` text,
  `level_id` int(11) NOT NULL DEFAULT '0',
  `reset_key` varchar(32) NOT NULL DEFAULT '0',
  `u_last_post_id` int(11) NOT NULL DEFAULT '0',
  `home_page` varchar(255) DEFAULT NULL,
  `bio` text,
  `cat_collapse_status` text,
  `custom_color` varchar(255) DEFAULT NULL,
  `buddy_list` text,
  `ignore_list` text,
  `group_leader_list` text,
  `users_opt` int(11) NOT NULL DEFAULT '4488117',
  `egw_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `login` (`login`),
  UNIQUE KEY `alias` (`alias`),
  UNIQUE KEY `egw_id` (`egw_id`),
  KEY `conf_key` (`conf_key`),
  KEY `last_visit` (`last_visit`),
  KEY `referer_id` (`referer_id`),
  KEY `reset_key` (`reset_key`),
  KEY `users_opt` (`users_opt`),
  KEY `email` (`email`)
) ENGINE=MyISAM AUTO_INCREMENT=152 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-01-21  9:53:24
