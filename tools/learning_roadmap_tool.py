"""
tools/learning_roadmap_tool.py

Custom CrewAI tool: nhận danh sách missing skills + experience_level
→ trả về roadmap học tập với resource thực tế.

Cải thiện v2:
- Thêm param experience_level để filter resources phù hợp theo level
- LLM fallback khi skill không có trong ROADMAP tĩnh
- Mở rộng ROADMAP thêm ~15 skills phổ biến
"""

import os
import json
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional

# ── Roadmap data ───────────────────────────────────────────────────────────────
# resources có thêm field "level_target": ["intern","fresher","junior","mid","senior"]
# để filter theo experience level của ứng viên

ROADMAP: dict[str, dict] = {
    # ── DevOps / Cloud ────────────────────────────────────────────────────────
    "docker": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Docker Official Docs: https://docs.docker.com/get-started/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - TechWorld with Nana (Docker full course): https://youtu.be/3c-iBn73dDE", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Docker & Kubernetes (Mumshad): https://www.udemy.com/course/learn-docker/", "for": ["fresher","junior","mid"]},
            {"text": "📘 Docker Compose deep dive: https://docs.docker.com/compose/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "kubernetes": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Kubernetes Official Docs: https://kubernetes.io/docs/tutorials/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - TechWorld with Nana (K8s): https://youtu.be/X48VuDVv0do", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Kubernetes for Absolute Beginners: https://www.udemy.com/course/learn-kubernetes/", "for": ["intern","fresher","junior"]},
            {"text": "🏆 Chứng chỉ khuyên dùng: CKA (Certified Kubernetes Administrator)", "for": ["junior","mid","senior"]},
            {"text": "📘 Kubernetes Patterns (O'Reilly): https://k8spatterns.io/", "for": ["mid","senior"]},
        ],
        "estimated_time": {"intern": "8-10 tuần", "fresher": "5-6 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "terraform": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Terraform Docs: https://developer.hashicorp.com/terraform/tutorials", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - freeCodeCamp Terraform: https://youtu.be/SLB_c_ayRMo", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Terraform Beginner to Advanced: https://www.udemy.com/course/terraform-beginner-to-advanced/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: HashiCorp Terraform Associate", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "5-6 tuần", "fresher": "3-4 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "< 1 tuần"},
    },
    "aws": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 AWS Skill Builder (free): https://skillbuilder.aws/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - freeCodeCamp AWS: https://youtu.be/ulprqHHWlng", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - AWS Certified Solutions Architect: https://www.udemy.com/course/aws-certified-solutions-architect-associate/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: AWS Cloud Practitioner (entry level, phù hợp intern/fresher)", "for": ["intern","fresher"]},
            {"text": "🏆 Chứng chỉ: AWS SAA-C03 (associate, phù hợp junior+)", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "8-10 tuần", "fresher": "6-8 tuần", "junior": "4-5 tuần", "mid": "2-3 tuần", "senior": "1-2 tuần"},
    },
    "ci/cd": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 GitHub Actions Docs: https://docs.github.com/en/actions", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - TechWorld with Nana CI/CD: https://youtu.be/R8_veQiYBjI", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Jenkins Pipeline: https://www.udemy.com/course/jenkins-from-zero-to-hero/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "jenkins": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Jenkins Docs: https://www.jenkins.io/doc/tutorials/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Jenkins Tutorial for Beginners: https://youtu.be/FX322RVNGj4", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - Jenkins From Zero To Hero: https://www.udemy.com/course/jenkins-from-zero-to-hero/", "for": ["fresher","junior"]},
        ],
        "estimated_time": {"intern": "3 tuần", "fresher": "2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "linux": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Linux Journey (free): https://linuxjourney.com/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Linux Full Course freeCodeCamp: https://youtu.be/sWbUDq4S6Y8", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - Linux Administration Bootcamp: https://www.udemy.com/course/linux-administration-bootcamp/", "for": ["fresher","junior","mid"]},
            {"text": "📘 Linux Command Line (free book): https://linuxcommand.org/tlcl.php", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "5-6 tuần", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "ansible": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Ansible Docs: https://docs.ansible.com/ansible/latest/getting_started/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Ansible Tutorial for Beginners: https://youtu.be/1id6ERvfozo", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Ansible for Beginners: https://www.udemy.com/course/learn-ansible/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "4-5 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    # ── Network / System ──────────────────────────────────────────────────────
    "ccna": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Cisco Learning Network: https://learningnetwork.cisco.com/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Jeremy's IT Lab CCNA: https://youtube.com/playlist?list=PLxbwE86jKRgMpuZuLBivzlM8s2Dk5lXBQ", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - CCNA 200-301 Complete Course: https://www.udemy.com/course/ccna-complete/", "for": ["intern","fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: Cisco CCNA 200-301", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "12-16 tuần", "fresher": "8-12 tuần", "junior": "6-8 tuần", "mid": "4 tuần", "senior": "2-3 tuần"},
    },
    "networking": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Cisco Networking Academy (free): https://www.netacad.com/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - NetworkChuck Networking: https://youtu.be/qiQR5rTSshw", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - The Complete Networking Fundamentals: https://www.udemy.com/course/complete-networking-fundamentals-course-ccna-start/", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "< 1 tuần"},
    },
    "firewall": {
        "level": "Intermediate",
        "resources": [
            {"text": "🎬 YouTube - Fortinet NSE Training: https://training.fortinet.com/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - pfSense Firewall Tutorial: https://youtu.be/fsdm5uc_LsU", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Palo Alto PCNSA: https://www.udemy.com/course/palo-alto-networks-firewall/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "4-5 tuần", "fresher": "3-4 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "vpn": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 OpenVPN Docs: https://openvpn.net/community-resources/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - VPN Concepts: https://youtu.be/R-JUOpCgTZc", "for": ["intern","fresher"]},
        ],
        "estimated_time": {"intern": "2 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    # ── Software Development ──────────────────────────────────────────────────
    "java": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Java Official Tutorials: https://docs.oracle.com/javase/tutorial/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Java Full Course freeCodeCamp: https://youtu.be/GoXwIVyNvX0", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - Java Masterclass: https://www.udemy.com/course/java-the-complete-java-developer-course/", "for": ["intern","fresher","junior"]},
            {"text": "📘 Effective Java (Joshua Bloch): https://www.oreilly.com/library/view/effective-java/9780134686097/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "12-16 tuần", "fresher": "8-12 tuần", "junior": "4-6 tuần", "mid": "2-3 tuần", "senior": "1-2 tuần"},
    },
    "spring boot": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Spring Docs: https://spring.io/guides", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Amigoscode Spring Boot: https://youtu.be/9SGDpanrc8U", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Spring Boot 3 & Spring Framework 6: https://www.udemy.com/course/spring-hibernate-tutorial/", "for": ["fresher","junior","mid"]},
            {"text": "📘 Spring Security in Action: https://www.manning.com/books/spring-security-in-action-second-edition", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "8-10 tuần", "fresher": "5-6 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "python": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Python Official Tutorial: https://docs.python.org/3/tutorial/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Python freeCodeCamp: https://youtu.be/rfscVS0vtbw", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - Complete Python Bootcamp: https://www.udemy.com/course/complete-python-bootcamp/", "for": ["intern","fresher","junior"]},
            {"text": "📘 Fluent Python (O'Reilly): https://www.oreilly.com/library/view/fluent-python-2nd/9781492056348/", "for": ["mid","senior"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "< 1 tuần"},
    },
    "reactjs": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 React Official Docs: https://react.dev/learn", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - React Full Course freeCodeCamp: https://youtu.be/bMknfKXIFA8", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - React The Complete Guide: https://www.udemy.com/course/react-the-complete-guide-incl-redux/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "8-10 tuần", "fresher": "6-8 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "typescript": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 TypeScript Docs: https://www.typescriptlang.org/docs/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - TypeScript Full Course: https://youtu.be/30LWjhZzg50", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Understanding TypeScript: https://www.udemy.com/course/understanding-typescript/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "sql": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 SQLZoo (free interactive): https://sqlzoo.net/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - SQL Full Course freeCodeCamp: https://youtu.be/HXV3zeQKqGY", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - The Complete SQL Bootcamp: https://www.udemy.com/course/the-complete-sql-bootcamp/", "for": ["intern","fresher","junior"]},
            {"text": "📘 Use The Index, Luke (advanced SQL): https://use-the-index-luke.com/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "rest api": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 REST API Tutorial: https://restfulapi.net/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - REST API Crash Course: https://youtu.be/-MTSQjw5DrM", "for": ["intern","fresher"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "microservices": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Microservices.io Patterns: https://microservices.io/patterns/", "for": ["junior","mid","senior"]},
            {"text": "🎬 YouTube - Microservices with Spring Boot: https://youtu.be/BnknNTN8icw", "for": ["junior","mid"]},
            {"text": "🎓 Udemy - Microservices with Spring Boot & Spring Cloud: https://www.udemy.com/course/microservices-with-spring-boot-and-spring-cloud/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "10-12 tuần", "junior": "6-8 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    # ── IT Support / System ───────────────────────────────────────────────────
    "active directory": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Microsoft Learn AD: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Active Directory Tutorial: https://youtu.be/85-bp7XxWDQ", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Windows Server Administration: https://www.udemy.com/course/windows-server-administration/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "vmware": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 VMware Learning: https://www.vmware.com/learning.html", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - VMware ESXi Tutorial: https://youtu.be/KoFMfFEDFKw", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - VMware vSphere 8: https://www.udemy.com/course/vmware-vsphere-67-bootcamp/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: VMware VCP-DCV", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    # ── Security ──────────────────────────────────────────────────────────────
    "security": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 OWASP Top 10: https://owasp.org/www-project-top-ten/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Cybersecurity Full Course: https://youtu.be/U_P23SqJaDc", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - The Complete Cyber Security Course: https://www.udemy.com/course/the-complete-internet-security-privacy-course-volume-1/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: CompTIA Security+", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "8-10 tuần", "fresher": "6-8 tuần", "junior": "4-5 tuần", "mid": "2-3 tuần", "senior": "1-2 tuần"},
    },
    # ── Monitoring ────────────────────────────────────────────────────────────
    "prometheus": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Prometheus Docs: https://prometheus.io/docs/introduction/overview/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Prometheus & Grafana Tutorial: https://youtu.be/h4Sl21AKiDg", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "grafana": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Grafana Docs: https://grafana.com/docs/grafana/latest/getting-started/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Grafana Tutorial for Beginners: https://youtu.be/lILY8eSspEo", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "1-2 tuần", "fresher": "1 tuần", "junior": "< 1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "git": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Git Official Docs: https://git-scm.com/doc", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Git & GitHub freeCodeCamp: https://youtu.be/RGOj5yH7evk", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - Git Complete: https://www.udemy.com/course/git-complete/", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "redis": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Redis Docs: https://redis.io/docs/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Redis Crash Course: https://youtu.be/jgpVdJB2sKQ", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "mongodb": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 MongoDB University (free): https://learn.mongodb.com/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - MongoDB Crash Course: https://youtu.be/ofme2o29ngU", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - MongoDB The Complete Guide: https://www.udemy.com/course/mongodb-the-complete-developers-guide/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "nginx": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 NGINX Docs: https://nginx.org/en/docs/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - NGINX Tutorial: https://youtu.be/7VAI73roXaY", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "1-2 tuần", "fresher": "1 tuần", "junior": "< 1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "nodejs": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Node.js Docs: https://nodejs.org/en/docs/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Node.js freeCodeCamp: https://youtu.be/Oe421EPjeBE", "for": ["intern","fresher"]},
            {"text": "🎓 Udemy - NodeJS - The Complete Guide: https://www.udemy.com/course/nodejs-the-complete-guide/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "github actions": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 GitHub Actions Docs: https://docs.github.com/en/actions", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - GitHub Actions Tutorial: https://youtu.be/R8_veQiYBjI", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "2 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "helm": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Helm Docs: https://helm.sh/docs/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Helm Tutorial: https://youtu.be/5_J7RWLLVeQ", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    # ── Mới thêm v2 ───────────────────────────────────────────────────────────
    "argocd": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 ArgoCD Docs: https://argo-cd.readthedocs.io/en/stable/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - ArgoCD Tutorial: https://youtu.be/MeU5_k9ssrs", "for": ["fresher","junior"]},
            {"text": "🏆 Chứng chỉ liên quan: CKA/CKAD (Kubernetes foundation trước)", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Cần Kubernetes trước", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "elasticsearch": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Elasticsearch Docs: https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started.html", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Elasticsearch Tutorial: https://youtu.be/C3tlMqaNSaI", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Complete Elasticsearch Masterclass: https://www.udemy.com/course/elasticsearch-complete-guide/", "for": ["junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "kafka": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Apache Kafka Docs: https://kafka.apache.org/documentation/", "for": ["junior","mid","senior"]},
            {"text": "🎬 YouTube - Kafka Tutorial for Beginners: https://youtu.be/aj9CDZm0Glc", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Apache Kafka Series: https://www.udemy.com/course/apache-kafka/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp", "fresher": "4-5 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "postgresql": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 PostgreSQL Tutorial: https://www.postgresqltutorial.com/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - PostgreSQL Full Course: https://youtu.be/qw--VYLpxG4", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "go": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Go Official Tour: https://go.dev/tour/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Go / Golang Crash Course: https://youtu.be/SqrbIlUwR0U", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Go The Complete Developer's Guide: https://www.udemy.com/course/go-the-complete-developers-guide/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-5 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "monitoring": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Prometheus + Grafana stack: https://prometheus.io/docs/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Monitoring with Prometheus & Grafana: https://youtu.be/h4Sl21AKiDg", "for": ["intern","fresher","junior"]},
            {"text": "📘 Datadog Learning Center (free): https://learn.datadoghq.com/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "log management": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 ELK Stack Tutorial: https://www.elastic.co/what-is/elk-stack", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - ELK Stack Crash Course: https://youtu.be/4X0WLg05ASw", "for": ["intern","fresher","junior"]},
            {"text": "📘 Grafana Loki Docs: https://grafana.com/docs/loki/latest/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "backup": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Veeam Learning: https://www.veeam.com/free-courses.html", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Backup & Recovery Fundamentals: https://youtu.be/TE6sGPNM7EU", "for": ["intern","fresher"]},
            {"text": "📘 Restic Backup Docs (open source): https://restic.readthedocs.io/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "1-2 tuần", "fresher": "1 tuần", "junior": "< 1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "network security": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 OWASP Network Security: https://owasp.org/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Network Security Full Course: https://youtu.be/E03gh1huvW4", "for": ["intern","fresher","junior"]},
            {"text": "🏆 Chứng chỉ: CompTIA Network+ → CompTIA Security+", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "troubleshooting": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 CompTIA A+ Troubleshooting Guide: https://www.comptia.org/certifications/a", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - IT Troubleshooting Methodology: https://youtu.be/hFa_K2yMjnE", "for": ["intern","fresher"]},
            {"text": "📘 The Practice of System and Network Administration: https://www.amazon.com/Practice-System-Network-Administration-Enterprise/dp/0321919165", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần (lý thuyết)", "fresher": "1-2 tuần", "junior": "Thực hành tích lũy", "mid": "Thực hành tích lũy", "senior": "Thực hành tích lũy"},
    },
}

# Alias map
ALIASES: dict[str, str] = {
    "k8s": "kubernetes",
    "react": "reactjs",
    "react.js": "reactjs",
    "js": "javascript",
    "ts": "typescript",
    "ad": "active directory",
    "network": "networking",
    "networks": "networking",
    "tcp/ip": "networking",
    "lan/wan": "networking",
    "spring": "spring boot",
    "springboot": "spring boot",
    "infosec": "security",
    "cybersecurity": "security",
    "it security": "security",
    "prom": "prometheus",
    "gh actions": "github actions",
    "mongo": "mongodb",
    "node": "nodejs",
    "node.js": "nodejs",
    "postgres": "postgresql",
    "psql": "postgresql",
    "elastic": "elasticsearch",
    "elk": "elasticsearch",
    "golang": "go",
    "siem": "security",
    "ids/ips": "network security",
    "ids": "network security",
    "ips": "network security",
    "log": "log management",
    "logging": "log management",
    "loki": "log management",
}

VALID_LEVELS = ["intern", "fresher", "junior", "mid", "senior"]


def _normalize(skill: str) -> str:
    key = skill.lower().strip()
    return ALIASES.get(key, key)


def _lookup_static(skill: str, level: str) -> Optional[str]:
    """Tra cứu trong ROADMAP tĩnh, filter theo level."""
    key = _normalize(skill)

    data = None
    matched_key = None

    if key in ROADMAP:
        data = ROADMAP[key]
        matched_key = key
    else:
        for rkey, rdata in ROADMAP.items():
            if rkey in key or key in rkey:
                data = rdata
                matched_key = rkey
                break

    if not data:
        return None

    # Filter resources theo level
    filtered_resources = [
        r["text"] for r in data["resources"]
        if level in r["for"]
    ]
    if not filtered_resources:
        # Fallback: lấy resources của level gần nhất
        filtered_resources = [r["text"] for r in data["resources"]]

    time_est = data["estimated_time"]
    if isinstance(time_est, dict):
        time_str = time_est.get(level, time_est.get("fresher", "N/A"))
    else:
        time_str = time_est

    display_name = skill.title() if matched_key == key else f"{skill.title()} (gần với '{matched_key}')"
    lines = [
        f"**{display_name}** [{data['level']}] — ⏱ {time_str} (với level {level})",
    ] + filtered_resources
    return "\n".join(lines)


def _lookup_with_llm_fallback(skill: str, level: str) -> str:
    """Dùng LLM để tạo roadmap khi không có trong ROADMAP tĩnh."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return (
            f"**{skill.title()}**: Chưa có roadmap cụ thể. "
            f"Tìm trên: https://roadmap.sh | "
            f"https://www.udemy.com/courses/search/?q={skill.replace(' ', '+')}"
        )

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        prompt = f"""Tạo roadmap học tập ngắn gọn cho kỹ năng IT: "{skill}"
Người học là: {level} (intern/fresher/junior/mid/senior)

Trả về JSON hợp lệ DUY NHẤT, không kèm text ngoài:
{{
  "level_label": "<Beginner|Intermediate|Advanced>",
  "estimated_time": "<ví dụ: 2-3 tuần>",
  "resources": [
    "<resource 1 với link thực tế>",
    "<resource 2>",
    "<resource 3>"
  ]
}}

Yêu cầu:
- Phù hợp với level {level}
- Resources là link Udemy, YouTube, hoặc official docs thực tế
- Tối đa 3 resources"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()

        # Parse JSON
        import re
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(raw)

        lines = [
            f"**{skill.title()}** [{data.get('level_label', 'Unknown')}] "
            f"— ⏱ {data.get('estimated_time', 'N/A')} (với level {level})",
            "*(Roadmap được tạo bởi AI — kiểm tra link trước khi dùng)*",
        ] + data.get("resources", [])
        return "\n".join(lines)

    except Exception as e:
        # Fallback cuối cùng nếu LLM cũng fail
        return (
            f"**{skill.title()}**: Chưa có roadmap cụ thể. "
            f"Gợi ý tìm trên: https://roadmap.sh/roadmaps | "
            f"https://www.udemy.com/courses/search/?q={skill.replace(' ', '+')} "
            f"(lỗi LLM: {str(e)[:80]})"
        )


# ── Tool schema ────────────────────────────────────────────────────────────────

class LearningRoadmapInput(BaseModel):
    missing_skills: str = Field(
        description=(
            "Danh sách kỹ năng còn thiếu, phân cách bởi dấu phẩy. "
            "Ví dụ: 'Docker, Kubernetes, Terraform'"
        )
    )
    experience_level: Optional[str] = Field(
        default="fresher",
        description=(
            "Level kinh nghiệm của ứng viên: intern | fresher | junior | mid | senior. "
            "Dùng để filter resources phù hợp. Mặc định: fresher."
        )
    )


class LearningRoadmapTool(BaseTool):
    name: str = "learning_roadmap_tool"
    description: str = (
        "Tra cứu lộ trình học tập và tài nguyên thực tế cho các kỹ năng IT còn thiếu. "
        "Input: danh sách skill phân cách bởi dấu phẩy + experience_level (intern/fresher/junior/mid/senior). "
        "Output: roadmap chi tiết với link khóa học, video, docs chính thức — "
        "được filter theo level phù hợp. Dùng LLM fallback khi skill chưa có trong database."
    )
    args_schema: Type[BaseModel] = LearningRoadmapInput

    def _run(self, missing_skills: str, experience_level: str = "fresher") -> str:
        skills = [s.strip() for s in missing_skills.split(",") if s.strip()]
        if not skills:
            return "Không có kỹ năng nào cần tra cứu."

        # Normalize level
        level = experience_level.lower().strip()
        if level not in VALID_LEVELS:
            level = "fresher"

        results = []
        for skill in skills[:8]:  # giới hạn 8 skills
            static = _lookup_static(skill, level)
            if static:
                results.append(static)
            else:
                # LLM fallback cho skill không có trong database
                results.append(_lookup_with_llm_fallback(skill, level))

        return "\n\n".join(results)