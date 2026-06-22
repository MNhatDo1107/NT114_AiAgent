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
    # ── AI / Machine Learning / Data Analysis ─────────────────────────────────
    "artificial intelligence": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Elements of AI (free): https://www.elementsofai.com/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - AI For Everyone preview (Andrew Ng): https://www.coursera.org/learn/ai-for-everyone", "for": ["intern","fresher","junior"]},
            {"text": "📘 Google AI Education: https://ai.google/education/", "for": ["intern","fresher","junior","mid"]},
            {"text": "🎓 Udemy - Artificial Intelligence A-Z: https://www.udemy.com/course/artificial-intelligence-az/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "machine learning": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Machine Learning Specialization (Andrew Ng, Coursera): https://www.coursera.org/specializations/machine-learning-introduction", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Machine Learning Full Course freeCodeCamp: https://youtu.be/NWONeJKn6kc", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Machine Learning A-Z: https://www.udemy.com/course/machinelearning/", "for": ["fresher","junior","mid"]},
            {"text": "📘 Kaggle Learn - Intro to Machine Learning (free): https://www.kaggle.com/learn/intro-to-machine-learning", "for": ["intern","fresher","junior"]},
            {"text": "📘 Hands-On Machine Learning (O'Reilly): https://www.oreilly.com/library/view/hands-on-machine-learning/9781098125967/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "10-12 tuần", "fresher": "8-10 tuần", "junior": "5-6 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "deep learning": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Deep Learning Specialization (DeepLearning.AI): https://www.coursera.org/specializations/deep-learning", "for": ["junior","mid","senior"]},
            {"text": "🎬 YouTube - fast.ai Practical Deep Learning: https://course.fast.ai/", "for": ["fresher","junior","mid"]},
            {"text": "🎓 Udemy - Deep Learning A-Z: https://www.udemy.com/course/deeplearning/", "for": ["junior","mid","senior"]},
            {"text": "📘 PyTorch Tutorials: https://pytorch.org/tutorials/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "10-12 tuần", "junior": "6-8 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "data analysis": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Google Data Analytics Professional Certificate: https://www.coursera.org/professional-certificates/google-data-analytics", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Data Analysis with Python freeCodeCamp: https://youtu.be/r-uOLxNrNk8", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Data Analysis with Pandas and Python: https://www.udemy.com/course/data-analysis-with-pandas/", "for": ["fresher","junior","mid"]},
            {"text": "📘 Kaggle Learn - Pandas (free): https://www.kaggle.com/learn/pandas", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "< 1 tuần"},
    },
    "data science": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 IBM Data Science Professional Certificate: https://www.coursera.org/professional-certificates/ibm-data-science", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Data Science Full Course freeCodeCamp: https://youtu.be/ua-CiDNNj30", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - The Data Science Course 2024: https://www.udemy.com/course/the-data-science-course-complete-data-science-bootcamp/", "for": ["fresher","junior","mid"]},
            {"text": "📘 Python Data Science Handbook (free online): https://jakevdp.github.io/PythonDataScienceHandbook/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "10-12 tuần", "fresher": "8-10 tuần", "junior": "4-5 tuần", "mid": "2-3 tuần", "senior": "1-2 tuần"},
    },
    "pandas": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Pandas Official Docs: https://pandas.pydata.org/docs/getting_started/index.html", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Pandas Tutorial Corey Schafer: https://youtu.be/ZyhVh-qRZPA", "for": ["intern","fresher","junior"]},
            {"text": "📘 Kaggle Learn - Pandas (free): https://www.kaggle.com/learn/pandas", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "numpy": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 NumPy Official Docs: https://numpy.org/doc/stable/user/absolute_beginners.html", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - NumPy Tutorial freeCodeCamp: https://youtu.be/QUT1VHiLmmI", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "2 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "data visualization": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Matplotlib Docs: https://matplotlib.org/stable/tutorials/index.html", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "📘 Seaborn Docs: https://seaborn.pydata.org/tutorial.html", "for": ["fresher","junior","mid"]},
            {"text": "🎬 YouTube - Data Visualization with Python: https://youtu.be/a9UrKTVEeZA", "for": ["intern","fresher","junior"]},
            {"text": "📘 Storytelling with Data (book): https://www.storytellingwithdata.com/book", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "excel": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Microsoft Excel Training: https://support.microsoft.com/en-us/excel", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Excel Full Course freeCodeCamp: https://youtu.be/Vl0H-qTclOg", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Microsoft Excel - Beginner to Advanced: https://www.udemy.com/course/microsoft-excel-2013-from-beginner-to-advanced-and-beyond/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "power bi": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Microsoft Learn - Power BI: https://learn.microsoft.com/en-us/training/powerplatform/power-bi", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Power BI Full Course freeCodeCamp: https://youtu.be/AGrl-H87pRU", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Microsoft Power BI Desktop: https://www.udemy.com/course/microsoft-power-bi-up-running-with-power-bi-desktop/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: Microsoft PL-300 (Power BI Data Analyst)", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "4-5 tuần", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "tableau": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Tableau Free Training Videos: https://www.tableau.com/learn/training", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Tableau Full Course Edureka: https://youtu.be/aHaOIvR00So", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Tableau 2024 A-Z: https://www.udemy.com/course/tableau10/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: Tableau Desktop Specialist", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "4-5 tuần", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "statistics": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Khan Academy Statistics (free): https://www.khanacademy.org/math/statistics-probability", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - StatQuest with Josh Starmer: https://youtube.com/playlist?list=PLblh5JKOoLUK0FLuzwntyYI10UQFUhsY9", "for": ["intern","fresher","junior"]},
            {"text": "📘 Think Stats (free book): https://greenteapress.com/wp/think-stats-2e/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "5-6 tuần", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "nlp": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Hugging Face NLP Course (free): https://huggingface.co/learn/nlp-course", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Stanford CS224N (NLP with Deep Learning): https://youtube.com/playlist?list=PLoROMvodv4rOSH4v6133s9LFPRHjEmbmJ", "for": ["junior","mid","senior"]},
            {"text": "📘 spaCy Docs: https://spacy.io/usage/spacy-101", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "8-10 tuần", "junior": "5-6 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "computer vision": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 OpenCV Docs: https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - OpenCV Course freeCodeCamp: https://youtu.be/oXlwWbU8l2o", "for": ["fresher","junior","mid"]},
            {"text": "🎓 Udemy - Deep Learning Computer Vision: https://www.udemy.com/course/master-deep-learning-computer-visiontm-cnn-ssd-yolo-gans/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "8-10 tuần", "junior": "5-6 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "tensorflow": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 TensorFlow Official Tutorials: https://www.tensorflow.org/tutorials", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - TensorFlow Full Course freeCodeCamp: https://youtu.be/tPYj3fFJGjk", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - TensorFlow Developer Certificate: https://www.udemy.com/course/tensorflow-developer-certificate-machine-learning-zero-to-mastery/", "for": ["junior","mid"]},
            {"text": "🏆 Chứng chỉ: TensorFlow Developer Certificate", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "8-10 tuần", "fresher": "6-8 tuần", "junior": "4-5 tuần", "mid": "2-3 tuần", "senior": "1-2 tuần"},
    },
    "pytorch": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 PyTorch Official Tutorials: https://pytorch.org/tutorials/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - PyTorch for Deep Learning freeCodeCamp: https://youtu.be/V_xro1bcAuA", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - PyTorch for Deep Learning Bootcamp: https://www.udemy.com/course/pytorch-for-deep-learning/", "for": ["junior","mid"]},
        ],
        "estimated_time": {"intern": "8-10 tuần", "fresher": "6-8 tuần", "junior": "4-5 tuần", "mid": "2-3 tuần", "senior": "1-2 tuần"},
    },
    "scikit-learn": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 scikit-learn Official Docs: https://scikit-learn.org/stable/getting_started.html", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "📘 Kaggle Learn - Intro to Machine Learning (free): https://www.kaggle.com/learn/intro-to-machine-learning", "for": ["intern","fresher","junior"]},
            {"text": "🎬 YouTube - scikit-learn Crash Course: https://youtu.be/0B5eIE_1vpU", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "generative ai": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Generative AI for Everyone (DeepLearning.AI): https://www.coursera.org/learn/generative-ai-for-everyone", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "📘 OpenAI Docs & Cookbook: https://platform.openai.com/docs/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Generative AI Explained (NVIDIA): https://youtu.be/G2fqAlgmoPo", "for": ["intern","fresher","junior"]},
            {"text": "📘 Prompt Engineering Guide: https://www.promptingguide.ai/", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "4-5 tuần", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "prompt engineering": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 ChatGPT Prompt Engineering for Developers (DeepLearning.AI, free): https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "📘 Prompt Engineering Guide: https://www.promptingguide.ai/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "📘 Anthropic Prompt Engineering Docs: https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "1-2 tuần", "fresher": "1 tuần", "junior": "< 1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "mlops": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Made With ML - MLOps Course (free): https://madewithml.com/", "for": ["junior","mid","senior"]},
            {"text": "📘 MLOps Specialization (Coursera/DeepLearning.AI): https://www.coursera.org/specializations/machine-learning-engineering-for-production-mlops", "for": ["junior","mid","senior"]},
            {"text": "🎬 YouTube - MLOps Zoomcamp (DataTalksClub): https://youtube.com/playlist?list=PL3MmuxUbc_hIUISrluw_A7wDSmfOhErJK", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "8-10 tuần", "junior": "5-6 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "pyspark": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Apache Spark Docs: https://spark.apache.org/docs/latest/api/python/getting_started/index.html", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - PySpark Tutorial freeCodeCamp: https://youtu.be/_C8kWso4ne4", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Taming Big Data with PySpark: https://www.udemy.com/course/taming-big-data-with-apache-spark-hands-on/", "for": ["junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "5-6 tuần", "junior": "3-4 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "airflow": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Apache Airflow Docs: https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Apache Airflow Tutorial: https://youtu.be/K9AnJ9_ZAXE", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - The Complete Hands-On Course to Master Apache Airflow: https://www.udemy.com/course/the-complete-hands-on-course-to-master-apache-airflow/", "for": ["junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "4-5 tuần", "junior": "2-3 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    # ── AI domain-specific skills (xuất hiện thực tế trong JD) ───────────────
    "feature engineering": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Kaggle Learn - Feature Engineering (free): https://www.kaggle.com/learn/feature-engineering", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Feature Engineering for Machine Learning: https://youtu.be/tayd6KBgHOI", "for": ["intern","fresher","junior"]},
            {"text": "📘 Feature Engineering for ML (book, Alice Zheng): https://www.oreilly.com/library/view/feature-engineering-for/9781491953235/", "for": ["junior","mid","senior"]},
            {"text": "🎓 Udemy - Feature Engineering for Machine Learning: https://www.udemy.com/course/feature-engineering-for-machine-learning/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "data preparation": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Kaggle Learn - Data Cleaning (free): https://www.kaggle.com/learn/data-cleaning", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Data Preprocessing in Python: https://youtu.be/0xVqLJe9_CY", "for": ["intern","fresher","junior"]},
            {"text": "📘 scikit-learn Preprocessing Guide: https://scikit-learn.org/stable/modules/preprocessing.html", "for": ["fresher","junior","mid"]},
            {"text": "🎓 Udemy - Data Analysis with Pandas and Python: https://www.udemy.com/course/data-analysis-with-pandas/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "data pipeline": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Apache Airflow Docs: https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Building Data Pipelines: https://youtu.be/K9AnJ9_ZAXE", "for": ["fresher","junior"]},
            {"text": "📘 DataTalksClub - Data Engineering Zoomcamp (free): https://github.com/DataTalksClub/data-engineering-zoomcamp", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎓 Udemy - Data Engineering with Python: https://www.udemy.com/course/data-engineering-using-apache-spark-python-and-delta-lake/", "for": ["junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "5-6 tuần", "junior": "3-4 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "recommendation engine": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Google Developers - Recommendation Systems (free): https://developers.google.com/machine-learning/recommendation", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Build a Recommendation System: https://youtu.be/G4MBc40rQ2k", "for": ["fresher","junior"]},
            {"text": "📘 Surprise Library Docs (CF algorithms): https://surpriselib.com/", "for": ["junior","mid"]},
            {"text": "🎓 Udemy - Recommender Systems and Deep Learning in Python: https://www.udemy.com/course/recommender-systems/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "8-10 tuần", "junior": "5-6 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "demand forecasting": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Kaggle - Store Sales Forecasting (hands-on): https://www.kaggle.com/competitions/store-sales-time-series-forecasting", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Time Series Forecasting Python: https://youtu.be/e8Yw4alG16Q", "for": ["fresher","junior"]},
            {"text": "📘 Nixtla - statsforecast (modern forecasting lib): https://github.com/Nixtla/statsforecast", "for": ["junior","mid","senior"]},
            {"text": "🎓 Udemy - Time Series Analysis & Forecasting: https://www.udemy.com/course/python-for-time-series-data-analysis/", "for": ["junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "6-8 tuần", "junior": "4-5 tuần", "mid": "2-3 tuần", "senior": "1-2 tuần"},
    },
    "clinical decision support": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 MIT OpenCourseWare - Machine Learning for Healthcare: https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/", "for": ["junior","mid","senior"]},
            {"text": "🎬 YouTube - AI in Healthcare (Andrew Ng, Coursera): https://www.coursera.org/specializations/ai-for-medicine", "for": ["junior","mid","senior"]},
            {"text": "📘 HL7 FHIR Docs (healthcare data standard): https://www.hl7.org/fhir/overview.html", "for": ["junior","mid","senior"]},
            {"text": "🎓 Coursera - AI for Medicine Specialization: https://www.coursera.org/specializations/ai-for-medicine", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "10-12 tuần", "junior": "6-8 tuần", "mid": "3-4 tuần", "senior": "2-3 tuần"},
    },
    "ai assistant": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 LangChain Docs (build AI apps): https://python.langchain.com/docs/get_started/introduction", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Build AI Assistant with LangChain: https://youtu.be/MlK6SIjcjE8", "for": ["fresher","junior"]},
            {"text": "📘 OpenAI Assistants API Docs: https://platform.openai.com/docs/assistants/overview", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎓 DeepLearning.AI - LangChain for LLM Application Development (free): https://www.deeplearning.ai/short-courses/langchain-for-llm-application-development/", "for": ["fresher","junior","mid","senior"]},
            {"text": "📘 Anthropic Claude API Docs: https://docs.anthropic.com/en/docs/", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "4-5 tuần", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "langchain": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 LangChain Official Docs: https://python.langchain.com/docs/get_started/introduction", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - LangChain Crash Course: https://youtu.be/LbT1yp6quS8", "for": ["fresher","junior"]},
            {"text": "🎓 DeepLearning.AI - LangChain for LLM Application Development (free): https://www.deeplearning.ai/short-courses/langchain-for-llm-application-development/", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "rag": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 LlamaIndex Docs (RAG framework): https://docs.llamaindex.ai/en/stable/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - RAG from Scratch: https://youtu.be/sVcwVQRHIc8", "for": ["fresher","junior"]},
            {"text": "🎓 DeepLearning.AI - Building and Evaluating Advanced RAG (free): https://www.deeplearning.ai/short-courses/building-evaluating-advanced-rag/", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "time series": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Kaggle - Time Series (free): https://www.kaggle.com/learn/time-series", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Time Series Analysis Python: https://youtu.be/e8Yw4alG16Q", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Time Series Analysis & Forecasting: https://www.udemy.com/course/python-for-time-series-data-analysis/", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    # ── Cloud AI / ML Platforms ───────────────────────────────────────────────
    "azure": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Microsoft Learn - Azure Fundamentals (free): https://learn.microsoft.com/en-us/training/paths/azure-fundamentals/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Azure Full Course freeCodeCamp: https://youtu.be/NKEFWyqJ5XA", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - AZ-900 Azure Fundamentals: https://www.udemy.com/course/az900-azure/", "for": ["intern","fresher","junior"]},
            {"text": "🏆 Chứng chỉ: AZ-900 → AZ-104 → DP-100 (Azure ML)", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "gcp": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Google Cloud Skills Boost (free tier): https://www.cloudskillsboost.google/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - GCP Full Course freeCodeCamp: https://youtu.be/jpno8FSqpc8", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Google Cloud Associate Cloud Engineer: https://www.udemy.com/course/google-cloud-associate-cloud-engineer/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: Google Cloud Associate Cloud Engineer", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "6-8 tuần", "fresher": "4-6 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "azure ml": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Azure Machine Learning Docs: https://learn.microsoft.com/en-us/azure/machine-learning/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Azure ML Tutorial: https://youtu.be/RqSlkXSPSbs", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Azure ML Engineer: https://www.udemy.com/course/azure-machine-learning-course/", "for": ["junior","mid"]},
            {"text": "🏆 Chứng chỉ: DP-100 Azure Data Scientist Associate", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "5-6 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "sagemaker": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 AWS SageMaker Docs: https://docs.aws.amazon.com/sagemaker/latest/dg/whatis.html", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - SageMaker Tutorial: https://youtu.be/uQc8Itd4UTs", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - AWS SageMaker Practical: https://www.udemy.com/course/practical-aws-sagemaker-6-real-world-case-studies/", "for": ["junior","mid"]},
            {"text": "🏆 Chứng chỉ: AWS Certified Machine Learning Specialty", "for": ["mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "4-5 tuần", "junior": "3-4 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "vertex ai": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Google Vertex AI Docs: https://cloud.google.com/vertex-ai/docs/start/introduction-unified-platform", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Vertex AI Tutorial: https://youtu.be/7dOsGwP8bEo", "for": ["fresher","junior"]},
            {"text": "📘 Google Cloud Skills Boost - ML Paths: https://www.cloudskillsboost.google/paths/17", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "4-5 tuần", "junior": "2-3 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    # ── Data Engineering ──────────────────────────────────────────────────────
    "data engineering": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 DataTalksClub - Data Engineering Zoomcamp (free): https://github.com/DataTalksClub/data-engineering-zoomcamp", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Data Engineering Course for Beginners: https://youtu.be/plyALs-P4EE", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - The Complete Hands-On Introduction to Apache Spark: https://www.udemy.com/course/apache-spark-course-with-java/", "for": ["junior","mid"]},
            {"text": "📘 Fundamentals of Data Engineering (O'Reilly): https://www.oreilly.com/library/view/fundamentals-of-data/9781098108298/", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "8-10 tuần", "junior": "5-6 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "dbt": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 dbt Official Docs: https://docs.getdbt.com/docs/introduction", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - dbt Tutorial for Beginners: https://youtu.be/5rNquRnNb4E", "for": ["intern","fresher","junior"]},
            {"text": "🎓 dbt Learn (free): https://courses.getdbt.com/collections", "for": ["intern","fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "snowflake": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Snowflake Docs: https://docs.snowflake.com/en/user-guide-getting-started.html", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Snowflake Tutorial for Beginners: https://youtu.be/9PBvVeCQi0w", "for": ["fresher","junior"]},
            {"text": "🎓 Snowflake University (free): https://university.snowflake.com/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🏆 Chứng chỉ: SnowPro Core Certification", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "3-4 tuần", "junior": "2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    # ── AI/ML specific techniques ─────────────────────────────────────────────
    "object detection": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Ultralytics YOLO Docs: https://docs.ultralytics.com/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - YOLO Object Detection: https://youtu.be/WgPbbWmnXJ8", "for": ["fresher","junior"]},
            {"text": "🎓 Udemy - Computer Vision with OpenCV & YOLO: https://www.udemy.com/course/computer-vision-masterclass/", "for": ["junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "6-8 tuần", "junior": "3-4 tuần", "mid": "2-3 tuần", "senior": "1 tuần"},
    },
    "image classification": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 fast.ai Practical Deep Learning (free): https://course.fast.ai/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Image Classification with CNN: https://youtu.be/7HPwo4wnJeA", "for": ["fresher","junior"]},
            {"text": "📘 TensorFlow Image Classification Tutorial: https://www.tensorflow.org/tutorials/images/classification", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "6-8 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "sentiment analysis": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Hugging Face - Sentiment Analysis Tutorial: https://huggingface.co/blog/sentiment-analysis-python", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Sentiment Analysis with Python: https://youtu.be/M7SWr5xObkA", "for": ["intern","fresher","junior"]},
            {"text": "📘 Kaggle - NLP Getting Started: https://www.kaggle.com/competitions/nlp-getting-started", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "text classification": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Hugging Face Text Classification: https://huggingface.co/docs/transformers/tasks/sequence_classification", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Text Classification with BERT: https://youtu.be/8N-nM3QW7O0", "for": ["fresher","junior"]},
            {"text": "📘 scikit-learn Text Feature Extraction: https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "3-4 tuần", "fresher": "2-3 tuần", "junior": "1-2 tuần", "mid": "1 tuần", "senior": "< 1 tuần"},
    },
    "transformers": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Hugging Face Transformers Docs: https://huggingface.co/docs/transformers/index", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Hugging Face Course: https://youtu.be/00GKzGyWFEs", "for": ["fresher","junior"]},
            {"text": "📘 Hugging Face NLP Course (free): https://huggingface.co/learn/nlp-course", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎓 DeepLearning.AI - Attention Mechanism & Transformers: https://www.coursera.org/learn/attention-models-in-nlp", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "8-10 tuần", "junior": "5-6 tuần", "mid": "3-4 tuần", "senior": "1-2 tuần"},
    },
    "fine-tuning": {
        "level": "Advanced",
        "resources": [
            {"text": "📘 Hugging Face - Fine-tuning Guide: https://huggingface.co/docs/transformers/training", "for": ["junior","mid","senior"]},
            {"text": "🎬 YouTube - Fine-tune LLM Tutorial: https://youtu.be/eC6Hd1hFvos", "for": ["fresher","junior"]},
            {"text": "🎓 DeepLearning.AI - Finetuning LLMs (free): https://www.deeplearning.ai/short-courses/finetuning-large-language-models/", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "6-8 tuần", "junior": "3-4 tuần", "mid": "2 tuần", "senior": "1 tuần"},
    },
    "vector database": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Pinecone Docs: https://docs.pinecone.io/docs/overview", "for": ["fresher","junior","mid","senior"]},
            {"text": "📘 Chroma Docs (open source): https://docs.trychroma.com/", "for": ["fresher","junior","mid"]},
            {"text": "🎬 YouTube - Vector Databases explained: https://youtu.be/dN0lsF2cvm4", "for": ["intern","fresher","junior"]},
            {"text": "🎓 DeepLearning.AI - Vector Databases: From Embeddings to Applications (free): https://www.deeplearning.ai/short-courses/vector-databases-embeddings-applications/", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "model deployment": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 FastAPI Docs (deploy ML model): https://fastapi.tiangolo.com/", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Deploy ML Model with FastAPI: https://youtu.be/b5F667g1yCk", "for": ["fresher","junior"]},
            {"text": "📘 BentoML Docs (ML serving): https://docs.bentoml.com/en/latest/", "for": ["junior","mid","senior"]},
            {"text": "🎓 DeepLearning.AI - ML in Production: https://www.coursera.org/specializations/machine-learning-engineering-for-production-mlops", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "4-5 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "a/b testing": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 Udacity - A/B Testing (free): https://www.udacity.com/course/ab-testing--ud257", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - A/B Testing Explained: https://youtu.be/TDD4AEvOp7I", "for": ["intern","fresher","junior"]},
            {"text": "📘 Trustworthy Online Controlled Experiments (book): https://www.cambridge.org/core/books/trustworthy-online-controlled-experiments/D97B26382EB0EB2DC2019A7A7B518F59", "for": ["mid","senior"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "model evaluation": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 scikit-learn Model Evaluation Guide: https://scikit-learn.org/stable/modules/model_evaluation.html", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - ML Model Evaluation Metrics: https://youtu.be/LbX4X71-TFI", "for": ["intern","fresher","junior"]},
            {"text": "📘 Kaggle - Intro to ML (metrics section, free): https://www.kaggle.com/learn/intermediate-machine-learning", "for": ["intern","fresher","junior"]},
        ],
        "estimated_time": {"intern": "1-2 tuần", "fresher": "1 tuần", "junior": "< 1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    # ── BI / Analytics tools ──────────────────────────────────────────────────
    "looker": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Looker Docs: https://cloud.google.com/looker/docs", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Looker Tutorial for Beginners: https://youtu.be/oV5cFm-C0-4", "for": ["intern","fresher","junior"]},
            {"text": "📘 Google Cloud Skills Boost - Looker: https://www.cloudskillsboost.google/paths/28", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "metabase": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Metabase Docs: https://www.metabase.com/docs/latest/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Metabase Tutorial: https://youtu.be/B3Z8FVi-4sY", "for": ["intern","fresher","junior"]},
            {"text": "📘 Metabase Learn (free): https://www.metabase.com/learn/", "for": ["intern","fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "1-2 tuần", "fresher": "1 tuần", "junior": "< 1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    # ── Soft skills / Process ─────────────────────────────────────────────────
    "agile": {
        "level": "Beginner",
        "resources": [
            {"text": "📘 Agile Alliance Resources: https://www.agilealliance.org/agile101/", "for": ["intern","fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Agile Methodology: https://youtu.be/Z9QbYZh1YXY", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Agile Scrum in Practice: https://www.udemy.com/course/agile-scrum/", "for": ["fresher","junior","mid"]},
            {"text": "🏆 Chứng chỉ: PSM I (Professional Scrum Master)", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "1-2 tuần", "fresher": "1 tuần", "junior": "< 1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "data governance": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 DAMA DMBOK Guide: https://www.dama.org/cpages/body-of-knowledge", "for": ["junior","mid","senior"]},
            {"text": "🎬 YouTube - Data Governance Explained: https://youtu.be/MeWNAqcBo6E", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Coursera - Data Governance: https://www.coursera.org/learn/data-governance", "for": ["fresher","junior","mid"]},
        ],
        "estimated_time": {"intern": "2-3 tuần", "fresher": "1-2 tuần", "junior": "1 tuần", "mid": "< 1 tuần", "senior": "< 1 tuần"},
    },
    "data warehouse": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 dbt Docs (data build tool): https://docs.getdbt.com/docs/introduction", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - Data Warehousing Concepts: https://youtu.be/AHR_7jFCMeY", "for": ["intern","fresher","junior"]},
            {"text": "🎓 Udemy - Data Warehouse Fundamentals: https://www.udemy.com/course/data-warehouse-the-ultimate-guide/", "for": ["fresher","junior","mid"]},
            {"text": "📘 BigQuery Docs (Google): https://cloud.google.com/bigquery/docs/introduction", "for": ["junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "4-5 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
    },
    "etl": {
        "level": "Intermediate",
        "resources": [
            {"text": "📘 dbt Docs - ETL/ELT guide: https://docs.getdbt.com/docs/introduction", "for": ["fresher","junior","mid","senior"]},
            {"text": "🎬 YouTube - ETL Pipeline Python Tutorial: https://youtu.be/dfouoh591Pc", "for": ["fresher","junior"]},
            {"text": "📘 DataTalksClub Data Engineering Zoomcamp (free): https://github.com/DataTalksClub/data-engineering-zoomcamp", "for": ["fresher","junior","mid","senior"]},
        ],
        "estimated_time": {"intern": "Chưa phù hợp ở level này", "fresher": "4-5 tuần", "junior": "2-3 tuần", "mid": "1-2 tuần", "senior": "1 tuần"},
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
    # ── AI / ML / Data Analysis aliases ─────────────────────────────────────
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "dl": "deep learning",
    "genai": "generative ai",
    "gen ai": "generative ai",
    "llm": "generative ai",
    "llms": "generative ai",
    "chatgpt": "generative ai",
    "natural language processing": "nlp",
    "sklearn": "scikit-learn",
    "tf": "tensorflow",
    "spark": "pyspark",
    "apache spark": "pyspark",
    "powerbi": "power bi",
    "power-bi": "power bi",
    "data viz": "data visualization",
    "dataviz": "data visualization",
    "stats": "statistics",
    "data analytics": "data analysis",
    "ms excel": "excel",
    "microsoft excel": "excel",
    # ── Domain-specific AI aliases ────────────────────────────────────────────
    "genai assistant": "ai assistant",
    "gen ai assistant": "ai assistant",
    "ai chatbot": "ai assistant",
    "llm assistant": "ai assistant",
    "chatbot": "ai assistant",
    "recsys": "recommendation engine",
    "recommender system": "recommendation engine",
    "recommendation system": "recommendation engine",
    "collaborative filtering": "recommendation engine",
    "forecasting": "demand forecasting",
    "time series forecasting": "demand forecasting",
    "sales forecasting": "demand forecasting",
    "clinical ai": "clinical decision support",
    "healthcare ai": "clinical decision support",
    "medical ai": "clinical decision support",
    "pipeline data": "data pipeline",
    "data pipelines": "data pipeline",
    "data prep": "data preparation",
    "data preprocessing": "data preparation",
    "data cleaning": "data preparation",
    "data wrangling": "data preparation",
    "feature selection": "feature engineering",
    "feature extraction": "feature engineering",
    "retrieval augmented generation": "rag",
    "retrieval-augmented generation": "rag",
    "timeseries": "time series",
    "time-series": "time series",
    "dwh": "data warehouse",
    "data mart": "data warehouse",
    "bigquery": "data warehouse",
    "redshift": "data warehouse",
    "extract transform load": "etl",
    "elt": "etl",
    # ── Cloud AI / ML Platform aliases ────────────────────────────────────────
    "microsoft azure": "azure",
    "azure cloud": "azure",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "aws ml": "sagemaker",
    "aws sagemaker": "sagemaker",
    "amazon sagemaker": "sagemaker",
    "google vertex": "vertex ai",
    "vertex": "vertex ai",
    "azure machine learning": "azure ml",
    # ── Data Engineering aliases ───────────────────────────────────────────────
    "data engineer": "data engineering",
    "data ops": "data engineering",
    "dataops": "data engineering",
    # ── AI technique aliases ───────────────────────────────────────────────────
    "hugging face": "transformers",
    "huggingface": "transformers",
    "bert": "transformers",
    "gpt": "transformers",
    "llm finetuning": "fine-tuning",
    "finetuning": "fine-tuning",
    "fine tuning": "fine-tuning",
    "lora": "fine-tuning",
    "qlora": "fine-tuning",
    "pinecone": "vector database",
    "chroma": "vector database",
    "weaviate": "vector database",
    "milvus": "vector database",
    "vector db": "vector database",
    "vector store": "vector database",
    "embedding": "vector database",
    "embeddings": "vector database",
    "yolo": "object detection",
    "cnn": "image classification",
    "convolutional neural network": "image classification",
    "nlp classification": "text classification",
    "ab testing": "a/b testing",
    "split testing": "a/b testing",
    "model serving": "model deployment",
    "ml deployment": "model deployment",
    "model scoring": "model evaluation",
    "metrics": "model evaluation",
    "accuracy precision recall": "model evaluation",
    # ── BI aliases ─────────────────────────────────────────────────────────────
    "looker studio": "looker",
    "google looker": "looker",
    "bi tool": "metabase",
    "business intelligence": "metabase",
    # ── Process aliases ────────────────────────────────────────────────────────
    "scrum": "agile",
    "kanban": "agile",
    "data quality": "data governance",
    "data catalog": "data governance",
    "data lineage": "data governance",
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