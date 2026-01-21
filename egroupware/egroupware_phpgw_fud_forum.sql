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
-- Table structure for table `phpgw_fud_forum`
--

DROP TABLE IF EXISTS `phpgw_fud_forum`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `phpgw_fud_forum` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cat_id` int(11) NOT NULL DEFAULT '0',
  `name` varchar(100) DEFAULT NULL,
  `descr` text,
  `post_passwd` varchar(32) DEFAULT NULL,
  `forum_icon` varchar(255) DEFAULT NULL,
  `date_created` bigint(20) NOT NULL DEFAULT '0',
  `thread_count` int(11) NOT NULL DEFAULT '0',
  `post_count` int(11) NOT NULL DEFAULT '0',
  `last_post_id` int(11) NOT NULL DEFAULT '0',
  `view_order` int(11) NOT NULL DEFAULT '0',
  `max_attach_size` int(11) NOT NULL DEFAULT '0',
  `max_file_attachments` int(11) NOT NULL DEFAULT '1',
  `moderators` text,
  `message_threshold` int(11) NOT NULL DEFAULT '0',
  `forum_opt` int(11) NOT NULL DEFAULT '16',
  PRIMARY KEY (`id`),
  KEY `cat_id` (`cat_id`),
  KEY `last_post_id` (`last_post_id`)
) ENGINE=MyISAM AUTO_INCREMENT=3 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-01-21  9:50:37
